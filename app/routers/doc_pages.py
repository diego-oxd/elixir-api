from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from app.db import (
    PostgresDatabase,
    add_item,
    delete_item,
    get_db_dependency,
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
    project_id: str, db: Annotated[PostgresDatabase, Depends(get_db_dependency)]
):
    """List all doc pages for a project (id and title only)."""
    items = get_items_by_filter(db, COLLECTION, {"project_id": project_id})
    return [{"id": str(item["_id"]), "title": item["title"]} for item in items]


@router.get("/doc-pages/{doc_page_id}", response_model=DocPageResponse)
def get_doc_page(doc_page_id: str, db: Annotated[PostgresDatabase, Depends(get_db_dependency)]):
    """Get a doc page by ID."""
    item = get_item_by_id(db, COLLECTION, doc_page_id)

    if not item:
        raise HTTPException(status_code=404, detail="Doc page not found")

    return _doc_to_response(item)


@router.post("/doc-pages", response_model=DocPageResponse, status_code=201)
def create_doc_page(
    doc_page: DocPageCreate, db: Annotated[PostgresDatabase, Depends(get_db_dependency)]
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
    db: Annotated[PostgresDatabase, Depends(get_db_dependency)],
):
    """Update a doc page."""
    update_data = updates.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="No update data provided")

    update_item(db, COLLECTION, doc_page_id, update_data)
    item = get_item_by_id(db, COLLECTION, doc_page_id)

    if not item:
        raise HTTPException(status_code=404, detail="Doc page not found")

    return _doc_to_response(item)


@router.delete("/doc-pages/{doc_page_id}", status_code=204)
def delete_doc_page(doc_page_id: str, db: Annotated[PostgresDatabase, Depends(get_db_dependency)]):
    """Delete a doc page."""
    deleted = delete_item(db, COLLECTION, doc_page_id)

    if not deleted:
        raise HTTPException(status_code=404, detail="Doc page not found")
