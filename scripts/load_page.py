"""Script to load JSON files into the pages collection."""

import json
import sys
from pathlib import Path

# Add parent directory to path to import app modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.db import (
    add_item,
    get_db,
    get_item_by_composite_key,
    get_item_by_id,
    update_item,
)


def load_page_from_json(
    project_id: str,
    name: str,
    title: str,
    file_path: str,
    db_name: str | None = None,
) -> dict:
    """
    Load a JSON file and save its contents to the pages collection.

    Args:
        project_id: ID of the project this page belongs to
        name: Unique name/identifier for the page within the project
        title: Display title for the page
        file_path: Path to the JSON file to load
        db_name: Optional database name (defaults to env var or 'app')

    Returns:
        dict: The created or updated page document with id field

    Raises:
        FileNotFoundError: If the JSON file doesn't exist
        ValueError: If the JSON file is invalid or project doesn't exist
    """
    # Validate file exists
    path = Path(file_path)
    print(path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    # Read and parse JSON file
    try:
        with open(path, "r", encoding="utf-8") as f:
            json_data = json.load(f)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON file: {e}")

    # Serialize JSON to string for storage
    content = json.dumps(json_data, indent=2)

    with get_db(db_name) as db:
        # Validate project exists
        project = get_item_by_id(db, "projects", project_id)
        if not project:
            raise ValueError(f"Project with id '{project_id}' does not exist")

        # Check if page already exists with this (project_id, name)
        existing_page = get_item_by_composite_key(db, "pages", project_id, name)

        if existing_page:
            # Update existing page
            updates = {
                "title": title,
                "content": content,
            }
            update_item(db, "pages", existing_page["_id"], updates)

            # Fetch updated document
            updated_page = get_item_by_id(db, "pages", existing_page["_id"])
            result = {**updated_page}
            result["id"] = str(result.pop("_id"))

            print(f"✓ Updated existing page: {name} (id: {result['id']})")
            return result
        else:
            # Create new page
            page_doc = {
                "project_id": project_id,
                "name": name,
                "title": title,
                "content": content,
            }

            insert_result = add_item(db, "pages", page_doc)
            page_doc["_id"] = insert_result.inserted_id

            result = {**page_doc}
            result["id"] = str(result.pop("_id"))

            print(f"✓ Created new page: {name} (id: {result['id']})")
            return result


if __name__ == "__main__":

    project_id = "69782326f8080cd90c7cf5eb"
    page_name = "api"
    page_title = "API Overview"
    file_path = "./scripts/outputs/api.json"

    # Example usage - update these values as needed
    result = load_page_from_json(
        project_id=project_id,
        name=page_name,
        title=page_title,
        file_path=file_path,
    )
    print(f"\nPage saved successfully!")
    print(f"ID: {result['id']}")
    print(f"Name: {result['name']}")
    print(f"Title: {result['title']}")
    print(f"Project ID: {result['project_id']}")
