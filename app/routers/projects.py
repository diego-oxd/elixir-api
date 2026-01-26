from typing import Annotated

from bson.errors import InvalidId
from fastapi import APIRouter, Depends, HTTPException
from pymongo.database import Database

from app.db import add_item, delete_item, get_item_by_id, get_items
from app.models.schemas import (
    ProjectCreate,
    ProjectListItem,
    ProjectResponse,
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
    """List all projects (id and name only)."""
    items = get_items(db, COLLECTION)
    return [{"id": str(item["_id"]), "name": item["name"]} for item in items]


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
    """Delete a project."""
    try:
        deleted = delete_item(db, COLLECTION, project_id)
    except InvalidId:
        raise HTTPException(status_code=404, detail="Project not found")

    if not deleted:
        raise HTTPException(status_code=404, detail="Project not found")
