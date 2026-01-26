from typing import Annotated

from bson import ObjectId
from bson.errors import InvalidId
from fastapi import APIRouter, Depends, HTTPException
from pymongo.database import Database

from app.db import (
    add_item,
    delete_item,
    get_item_by_id,
    get_items_by_filter,
    update_item,
)
from app.models.schemas import (
    DocPageCreate,
    DocPageListItem,
    DocPageResponse,
    DocPageUpdate,
)

router = APIRouter(tags=["doc-pages"])

COLLECTION = "doc_pages"


def get_database():
    from app.main import get_db_dependency

    return get_db_dependency()


def _doc_to_response(doc: dict) -> dict:
    """Convert MongoDB document to response format."""
    result = {**doc}
    result["id"] = str(result.pop("_id"))
    return result


@router.get(
    "/projects/{project_id}/doc-pages",
    response_model=list[DocPageListItem],
)
def list_doc_pages_by_project(
    project_id: str, db: Annotated[Database, Depends(get_database)]
):
    """List all doc pages for a project (id and title only)."""
    items = get_items_by_filter(db, COLLECTION, {"project_id": project_id})
    return [{"id": str(item["_id"]), "title": item["title"]} for item in items]


@router.get("/doc-pages/{doc_page_id}", response_model=DocPageResponse)
def get_doc_page(doc_page_id: str, db: Annotated[Database, Depends(get_database)]):
    """Get a doc page by ID."""
    try:
        item = get_item_by_id(db, COLLECTION, doc_page_id)
    except InvalidId:
        raise HTTPException(status_code=404, detail="Doc page not found")

    if not item:
        raise HTTPException(status_code=404, detail="Doc page not found")

    return _doc_to_response(item)


@router.post("/doc-pages", response_model=DocPageResponse, status_code=201)
def create_doc_page(
    doc_page: DocPageCreate, db: Annotated[Database, Depends(get_database)]
):
    """Create a new doc page."""
    doc = doc_page.model_dump()
    result = add_item(db, COLLECTION, doc)
    doc["_id"] = result.inserted_id
    return _doc_to_response(doc)


@router.patch("/doc-pages/{doc_page_id}", response_model=DocPageResponse)
def update_doc_page(
    doc_page_id: str,
    updates: DocPageUpdate,
    db: Annotated[Database, Depends(get_database)],
):
    """Update a doc page."""
    try:
        ObjectId(doc_page_id)
    except InvalidId:
        raise HTTPException(status_code=404, detail="Doc page not found")

    update_data = updates.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="No update data provided")

    update_item(db, COLLECTION, doc_page_id, update_data)
    item = get_item_by_id(db, COLLECTION, doc_page_id)

    if not item:
        raise HTTPException(status_code=404, detail="Doc page not found")

    return _doc_to_response(item)


@router.delete("/doc-pages/{doc_page_id}", status_code=204)
def delete_doc_page(doc_page_id: str, db: Annotated[Database, Depends(get_database)]):
    """Delete a doc page."""
    try:
        deleted = delete_item(db, COLLECTION, doc_page_id)
    except InvalidId:
        raise HTTPException(status_code=404, detail="Doc page not found")

    if not deleted:
        raise HTTPException(status_code=404, detail="Doc page not found")
