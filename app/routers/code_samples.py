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
    CodeSampleCreate,
    CodeSampleListItem,
    CodeSampleResponse,
    CodeSampleUpdate,
)

router = APIRouter(tags=["code-samples"])

COLLECTION = "code_samples"


def _doc_to_response(doc: dict) -> dict:
    """Convert MongoDB document to response format."""
    result = {**doc}
    result["id"] = str(result.pop("_id"))
    return result


@router.get(
    "/projects/{project_id}/code-samples",
    response_model=list[CodeSampleListItem],
)
def list_code_samples_by_project(
    project_id: str, db: Annotated[PostgresDatabase, Depends(get_db_dependency)]
):
    """List all code samples for a project (id and title only)."""
    items = get_items_by_filter(db, COLLECTION, {"project_id": project_id})
    return [{"id": str(item["_id"]), "title": item["title"]} for item in items]


@router.get("/code-samples/{sample_id}", response_model=CodeSampleResponse)
def get_code_sample(sample_id: str, db: Annotated[PostgresDatabase, Depends(get_db_dependency)]):
    """Get a code sample by ID."""
    item = get_item_by_id(db, COLLECTION, sample_id)

    if not item:
        raise HTTPException(status_code=404, detail="Code sample not found")

    return _doc_to_response(item)


@router.post("/code-samples", response_model=CodeSampleResponse, status_code=201)
def create_code_sample(
    sample: CodeSampleCreate, db: Annotated[PostgresDatabase, Depends(get_db_dependency)]
):
    """Create a new code sample."""
    doc = sample.model_dump()
    result = add_item(db, COLLECTION, doc)
    doc["_id"] = result.inserted_id
    return _doc_to_response(doc)


@router.patch("/code-samples/{sample_id}", response_model=CodeSampleResponse)
def update_code_sample(
    sample_id: str,
    updates: CodeSampleUpdate,
    db: Annotated[PostgresDatabase, Depends(get_db_dependency)],
):
    """Update a code sample."""
    update_data = updates.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="No update data provided")

    update_item(db, COLLECTION, sample_id, update_data)
    item = get_item_by_id(db, COLLECTION, sample_id)

    if not item:
        raise HTTPException(status_code=404, detail="Code sample not found")

    return _doc_to_response(item)


@router.delete("/code-samples/{sample_id}", status_code=204)
def delete_code_sample(sample_id: str, db: Annotated[PostgresDatabase, Depends(get_db_dependency)]):
    """Delete a code sample."""
    deleted = delete_item(db, COLLECTION, sample_id)

    if not deleted:
        raise HTTPException(status_code=404, detail="Code sample not found")
