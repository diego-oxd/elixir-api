from typing import Annotated

from bson import ObjectId
from bson.errors import InvalidId
from fastapi import APIRouter, Depends, HTTPException
from pymongo.database import Database

from app.db import (
    add_item,
    delete_item,
    delete_items_by_filter,
    get_item_by_id,
    get_items,
    update_item,
)
from app.models.schemas import (
    ProjectCreate,
    ProjectListItem,
    ProjectResponse,
    ProjectUpdate,
)

router = APIRouter(prefix="/projects", tags=["projects"])

COLLECTION = "projects"


def get_database():
    from app.main import get_db_dependency

    return get_db_dependency()


def _doc_to_response(doc: dict) -> dict:
    """Convert MongoDB document to response format."""
    result = {**doc}
    result["id"] = str(result.pop("_id"))
    return result


@router.get("", response_model=list[ProjectListItem])
def list_projects(db: Annotated[Database, Depends(get_database)]):
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
def get_project(project_id: str, db: Annotated[Database, Depends(get_database)]):
    """Get a project by ID."""
    try:
        item = get_item_by_id(db, COLLECTION, project_id)
    except InvalidId:
        raise HTTPException(status_code=404, detail="Project not found")

    if not item:
        raise HTTPException(status_code=404, detail="Project not found")

    return _doc_to_response(item)


@router.post("", response_model=ProjectResponse, status_code=201)
def create_project(
    project: ProjectCreate, db: Annotated[Database, Depends(get_database)]
):
    """Create a new project."""
    doc = project.model_dump()
    result = add_item(db, COLLECTION, doc)
    doc["_id"] = result.inserted_id
    return _doc_to_response(doc)


@router.delete("/{project_id}", status_code=204)
def delete_project(project_id: str, db: Annotated[Database, Depends(get_database)]):
    """Delete a project and all its associated items."""
    try:
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

    except InvalidId:
        raise HTTPException(status_code=404, detail="Project not found")


@router.patch("/{project_id}", response_model=ProjectResponse)
def update_project(
    project_id: str,
    updates: ProjectUpdate,
    db: Annotated[Database, Depends(get_database)],
):
    """Update a project."""
    try:
        ObjectId(project_id)
    except InvalidId:
        raise HTTPException(status_code=404, detail="Project not found")

    update_data = updates.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="No update data provided")

    update_item(db, COLLECTION, project_id, update_data)
    item = get_item_by_id(db, COLLECTION, project_id)

    if not item:
        raise HTTPException(status_code=404, detail="Project not found")

    return _doc_to_response(item)
