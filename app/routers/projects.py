import re
import shutil
import subprocess
from pathlib import Path
from typing import Annotated

import requests
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException

from app.db import (
    PostgresDatabase,
    add_item,
    delete_item,
    delete_items_by_filter,
    get_db_dependency,
    get_item_by_id,
    get_items,
    update_item,
)
from app.models.schemas import (
    AddCodebaseRequest,
    AddRepoRequest,
    ProjectCreate,
    ProjectListItem,
    ProjectResponse,
    ProjectUpdate,
)
from app.services.prompts import prompts
from app.services.agent import query_codebase_json

router = APIRouter(prefix="/projects", tags=["projects"])

COLLECTION = "projects"
REPOS_ROOT = Path(".repos")


def _doc_to_response(doc: dict) -> dict:
    """Convert MongoDB document to response format."""
    result = {**doc}
    result["id"] = str(result.pop("_id"))
    return result


def validate_github_url(url: str) -> tuple[bool, str | None]:
    """
    Validate GitHub URL and extract repo name.

    Returns:
        (is_valid, repo_name or error_message)
    """
    # Pattern: https://github.com/{owner}/{repo}(.git)?
    pattern = r"^https://github\.com/([^/]+)/([^/]+?)(\.git)?$"
    match = re.match(pattern, url)

    if not match:
        return False, "Invalid GitHub URL. Must be https://github.com/{owner}/{repo}"

    owner, repo_name, _ = match.groups()

    # Remove .git suffix if present
    if repo_name.endswith('.git'):
        repo_name = repo_name[:-4]

    # Validate no path traversal
    if '..' in repo_name or '/' in repo_name:
        return False, "Invalid repository name"

    return True, repo_name


def clone_repository(repo_url: str, repo_name: str) -> tuple[bool, str]:
    """
    Clone repository to .repos/{repo_name}.
    Deletes existing clone if present.

    Returns:
        (success, error_message or relative_path)
    """
    # Ensure .repos directory exists
    REPOS_ROOT.mkdir(exist_ok=True)

    clone_path = REPOS_ROOT / repo_name

    # Delete existing clone if present
    if clone_path.exists():
        print(f"[INFO] Removing existing clone at {clone_path}")
        shutil.rmtree(clone_path)

    # Clone repository
    try:
        print(f"[INFO] Cloning {repo_url} to {clone_path}")
        result = subprocess.run(
            ["git", "clone", repo_url, str(clone_path)],
            capture_output=True,
            text=True,
            timeout=300  # 5 minute timeout
        )

        if result.returncode != 0:
            error_msg = result.stderr or result.stdout or "Unknown error"
            return False, f"Git clone failed: {error_msg}"

        # Return relative path
        relative_path = str(clone_path)
        return True, relative_path

    except subprocess.TimeoutExpired:
        return False, "Clone operation timed out (5 minute limit)"
    except FileNotFoundError:
        return False, "git command not found. Is git installed?"
    except Exception as e:
        return False, f"Unexpected error during clone: {str(e)}"


# Title mapping for generated pages
PAGE_TITLES = {
    "api": "API Overview",
    "data_model": "Data Model",
    "frontend": "Frontend Components",
    "project_overview": "Project Overview",
}


def generate_documentation_background(project_id: str, repo_path: str, db: PostgresDatabase):
    """
    Background task that calls GraphRag service and saves generated pages.
    """
    print(f"[INFO] Starting documentation generation for project {project_id}, repo: {repo_path}")

    try:
        # 1. Call GraphRag service
        response = requests.post(
            "http://localhost:8001/scripts/generate_documentation",
            json={"repo_path": repo_path},
            timeout=1200  # 20 minutes
        )
        response.raise_for_status()
        data = response.json()

        print(f"[INFO] GraphRag returned successfully for project {project_id}")

        # 2. Delete existing pages for this project (replacement strategy)
        page_names = list(PAGE_TITLES.keys())
        deleted_count = delete_items_by_filter(
            db,
            "pages",
            {
                "project_id": project_id,
                "name": {"$in": page_names}
            }
        )
        print(f"[INFO] Deleted {deleted_count} existing pages for project {project_id}")

        # 3. Save new pages
        for name, content in data.items():
            if name in PAGE_TITLES:
                page_doc = {
                    "project_id": project_id,
                    "name": name,
                    "title": PAGE_TITLES[name],
                    "content": content,
                }
                add_item(db, "pages", page_doc)
                print(f"[INFO] Saved page '{name}' for project {project_id}")

        print(f"[INFO] Documentation generation completed for project {project_id}")

    except requests.exceptions.Timeout:
        print(f"[ERROR] Documentation generation timed out for project {project_id} (20 min limit)")
    except requests.exceptions.RequestException as e:
        print(f"[ERROR] GraphRag request failed for project {project_id}: {e}")
    except Exception as e:
        print(f"[ERROR] Documentation generation failed for project {project_id}: {e}")


async def generate_documentation_with_claude(
    project_id: str,
    repo_path: str,
    db: PostgresDatabase
):
    """
    Background task that uses Claude Agent SDK to generate documentation
    for all configured prompts and saves pages to the database.
    """
    print(f"[INFO] Starting Claude-based documentation generation for project {project_id}, repo: {repo_path}")

    try:
        # 1. Delete existing pages for this project (replacement strategy)
        page_names = list(prompts.keys())
        deleted_count = delete_items_by_filter(
            db,
            "pages",
            {
                "project_id": project_id,
                "name": {"$in": page_names}
            }
        )
        print(f"[INFO] Deleted {deleted_count} existing pages for project {project_id}")

        # 2. Generate documentation for each prompt
        for prompt_name, prompt_data in prompts.items():
            try:
                print(f"[INFO] Generating '{prompt_name}' documentation for project {project_id}")

                # Call Claude Agent SDK with structured output
                result = await query_codebase_json(
                    user_query=prompt_data["prompt_template"],
                    repo_path=repo_path,
                    response_model=prompt_data["schema"],
                )

                # Serialize Pydantic model to dict for JSONB storage
                content_dict = result.model_dump()

                # Get title from PAGE_TITLES or fallback to prompt name
                title = PAGE_TITLES.get(prompt_name, prompt_name.replace("_", " ").title())

                # Save page to database
                page_doc = {
                    "project_id": project_id,
                    "name": prompt_name,
                    "title": title,
                    "content": content_dict,
                }
                add_item(db, "pages", page_doc)
                print(f"[INFO] Saved page '{prompt_name}' for project {project_id}")

            except Exception as e:
                # Log error but continue with other prompts
                print(f"[ERROR] Failed to generate '{prompt_name}' for project {project_id}: {e}")
                continue

        print(f"[INFO] Claude-based documentation generation completed for project {project_id}")

    except Exception as e:
        print(f"[ERROR] Documentation generation failed for project {project_id}: {e}")


@router.get("", response_model=list[ProjectListItem])
def list_projects(db: Annotated[PostgresDatabase, Depends(get_db_dependency)]):
    """List all projects."""
    items = get_items(db, COLLECTION)
    return [
        {
            "id": str(item["_id"]),
            "name": item["name"],
            "description": item.get("description"),
            "repo_path": item.get("repo_path"),
            "repo_url": item.get("repo_url"),
        }
        for item in items
    ]


@router.get("/{project_id}", response_model=ProjectResponse)
def get_project(project_id: str, db: Annotated[PostgresDatabase, Depends(get_db_dependency)]):
    """Get a project by ID."""
    item = get_item_by_id(db, COLLECTION, project_id)

    if not item:
        raise HTTPException(status_code=404, detail="Project not found")

    return _doc_to_response(item)


@router.post("", response_model=ProjectResponse, status_code=201)
def create_project(
    project: ProjectCreate, db: Annotated[PostgresDatabase, Depends(get_db_dependency)]
):
    """Create a new project."""
    doc = project.model_dump()
    result = add_item(db, COLLECTION, doc)
    doc["_id"] = result.inserted_id
    return _doc_to_response(doc)


@router.delete("/{project_id}", status_code=204)
def delete_project(project_id: str, db: Annotated[PostgresDatabase, Depends(get_db_dependency)]):
    """Delete a project and all its associated items."""
    # Verify project exists first
    project = get_item_by_id(db, COLLECTION, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Delete all related items from each collection
    delete_items_by_filter(db, "pages", {"project_id": project_id})
    delete_items_by_filter(db, "code_samples", {"project_id": project_id})
    delete_items_by_filter(db, "doc_pages", {"project_id": project_id})

    # Finally delete the project itself
    deleted = delete_item(db, COLLECTION, project_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Project not found")


@router.patch("/{project_id}", response_model=ProjectResponse)
def update_project(
    project_id: str,
    updates: ProjectUpdate,
    db: Annotated[PostgresDatabase, Depends(get_db_dependency)],
):
    """Update a project."""
    update_data = updates.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="No update data provided")

    update_item(db, COLLECTION, project_id, update_data)
    item = get_item_by_id(db, COLLECTION, project_id)

    if not item:
        raise HTTPException(status_code=404, detail="Project not found")

    return _doc_to_response(item)


@router.post("/{project_id}/add-codebase", response_model=ProjectResponse)
def add_codebase(
    project_id: str,
    request: AddCodebaseRequest,
    background_tasks: BackgroundTasks,
    db: Annotated[PostgresDatabase, Depends(get_db_dependency)],
):
    """Update project repo_path and trigger background documentation generation."""
    # Update project's repo_path
    update_item(db, COLLECTION, project_id, {"repo_path": request.repo_path})
    item = get_item_by_id(db, COLLECTION, project_id)

    if not item:
        raise HTTPException(status_code=404, detail="Project not found")

    # Spawn background task for documentation generation
    background_tasks.add_task(
        generate_documentation_background,
        project_id,
        request.repo_path,
        db
    )

    return _doc_to_response(item)


@router.post("/{project_id}/add-repo", response_model=ProjectResponse)
def add_repo(
    project_id: str,
    request: AddRepoRequest,
    background_tasks: BackgroundTasks,
    db: Annotated[PostgresDatabase, Depends(get_db_dependency)],
):
    """
    Clone a GitHub repository and associate it with a project.

    This endpoint:
    1. Validates the GitHub URL
    2. Clones the repository to .repos/{repo_name}
    3. Stores the relative path and URL in the project record
    4. Spawns background task to generate documentation using Claude Agent SDK
    """
    # Verify project exists
    project = get_item_by_id(db, COLLECTION, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Validate GitHub URL
    is_valid, result = validate_github_url(request.repo_url)
    if not is_valid:
        raise HTTPException(status_code=400, detail=result)

    repo_name = result

    # Clone repository
    success, result = clone_repository(request.repo_url, repo_name)
    if not success:
        raise HTTPException(status_code=400, detail=result)

    repo_path = result  # Relative path like .repos/my-repo

    # Update project in database
    update_data = {
        "repo_path": repo_path,
        "repo_url": request.repo_url
    }
    update_item(db, COLLECTION, project_id, update_data)

    # Spawn background task for documentation generation using Claude SDK
    # background_tasks.add_task(
    #     generate_documentation_with_claude,
    #     project_id,
    #     repo_path,
    #     db
    # )

    # Fetch updated project
    updated_project = get_item_by_id(db, COLLECTION, project_id)

    print(f"[INFO] Successfully added repo {repo_name} to project {project_id}")

    return _doc_to_response(updated_project)
