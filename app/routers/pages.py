from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from app.db import (
    PostgresDatabase,
    add_item,
    delete_item,
    get_db_dependency,
    get_item_by_composite_key,
    get_item_by_id,
    update_item,
)
from app.models.schemas import PageCreate, PageResponse, PageUpdate

router = APIRouter(tags=["pages"])

COLLECTION = "pages"


def _doc_to_response(doc: dict) -> dict:
    """Convert MongoDB document to response format."""
    result = {**doc}
    result["id"] = str(result.pop("_id"))
    return result


@router.get(
    "/projects/{project_id}/pages/{name}",
    response_model=PageResponse,
)
def get_page_by_composite_key(
    project_id: str, name: str, db: Annotated[PostgresDatabase, Depends(get_db_dependency)]
):
    """Get a page by project_id and name."""
    item = get_item_by_composite_key(db, COLLECTION, project_id, name)

    if not item:
        raise HTTPException(status_code=404, detail="Page not found")

    return _doc_to_response(item)


@router.post("/pages", response_model=PageResponse, status_code=201)
def create_page(page: PageCreate, db: Annotated[PostgresDatabase, Depends(get_db_dependency)]):
    """Create a new page."""
    doc = page.model_dump()
    result = add_item(db, COLLECTION, doc)
    doc["_id"] = result.inserted_id
    return _doc_to_response(doc)


@router.patch("/pages/{page_id}", response_model=PageResponse)
def update_page(
    page_id: str,
    updates: PageUpdate,
    db: Annotated[PostgresDatabase, Depends(get_db_dependency)],
):
    """Update a page."""
    update_data = updates.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="No update data provided")

    update_item(db, COLLECTION, page_id, update_data)
    item = get_item_by_id(db, COLLECTION, page_id)

    if not item:
        raise HTTPException(status_code=404, detail="Page not found")

    return _doc_to_response(item)


@router.delete("/pages/{page_id}", status_code=204)
def delete_page(page_id: str, db: Annotated[PostgresDatabase, Depends(get_db_dependency)]):
    """Delete a page."""
    deleted = delete_item(db, COLLECTION, page_id)

    if not deleted:
        raise HTTPException(status_code=404, detail="Page not found")
