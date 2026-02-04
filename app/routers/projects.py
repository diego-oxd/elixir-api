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
    ProjectCreate,
    ProjectListItem,
    ProjectResponse,
    ProjectUpdate,
)

router = APIRouter(prefix="/projects", tags=["projects"])

COLLECTION = "projects"


def _doc_to_response(doc: dict) -> dict:
    """Convert MongoDB document to response format."""
    result = {**doc}
    result["id"] = str(result.pop("_id"))
    return result


# Title mapping for generated pages
PAGE_TITLES = {
    "api": "API Overview",
    "data_model": "Data Model",
    "frontend_components": "Frontend Components",
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
