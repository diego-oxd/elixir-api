"""Script to load JSON or Markdown files into the pages collection."""

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


def load_page(
    project_id: str,
    name: str,
    title: str,
    file_path: str,
    db_name: str | None = None,
) -> dict:
    """
    Load a JSON or Markdown file and save its contents to the pages collection.

    Automatically detects file type based on extension:
    - .json files: stored in the 'content' JSONB field (for structured data like API, data_model)
    - .md files: stored in the 'markdown_content' TEXT field (for overview, frontend)

    Args:
        project_id: ID of the project this page belongs to
        name: Unique name/identifier for the page within the project
        title: Display title for the page
        file_path: Path to the JSON or Markdown file to load
        db_name: Optional database name (defaults to env var or 'app')

    Returns:
        dict: The created or updated page document with id field

    Raises:
        FileNotFoundError: If the file doesn't exist
        ValueError: If the file format is invalid or project doesn't exist
    """
    # Validate file exists
    path = Path(file_path)
    print(f"Loading file: {path}")

    if not path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    # Detect file type and load content
    file_extension = path.suffix.lower()

    if file_extension == ".json":
        # JSON file - store in content field (JSONB)
        print("Detected: JSON file (will store in 'content' field)")
        try:
            with open(path, "r", encoding="utf-8") as f:
                json_data = json.load(f)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON file: {e}")

        # For JSON pages, we store the dict directly (db.py handles Json() wrapper)
        content_data = json_data
        markdown_data = None

    elif file_extension == ".md":
        # Markdown file - store in markdown_content field (TEXT)
        print("Detected: Markdown file (will store in 'markdown_content' field)")
        with open(path, "r", encoding="utf-8") as f:
            markdown_data = f.read()

        # For markdown pages, content is empty dict
        content_data = {}

    else:
        raise ValueError(f"Unsupported file type: {file_extension}. Use .json or .md files.")

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
                "content": content_data,
                "markdown_content": markdown_data,
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
                "content": content_data,
                "markdown_content": markdown_data,
            }

            insert_result = add_item(db, "pages", page_doc)
            page_doc["_id"] = insert_result.inserted_id

            result = {**page_doc}
            result["id"] = str(result.pop("_id"))

            print(f"✓ Created new page: {name} (id: {result['id']})")
            return result


# Legacy function for backward compatibility
def load_page_from_json(
    project_id: str,
    name: str,
    title: str,
    file_path: str,
    db_name: str | None = None,
) -> dict:
    """
    Legacy function - use load_page() instead.

    This function is kept for backward compatibility but simply calls load_page().
    """
    return load_page(project_id, name, title, file_path, db_name)


if __name__ == "__main__":
    # Configuration - update these values as needed
    project_id = "a4042b78-d583-41c7-b843-3460c5b5f2a3"
    page_name = "frontend"  # Unique name/identifier for the page
    page_title = "Frontend"  # Display title for the page

    # The script automatically detects file type by extension:
    # - Use .json for structured pages (api, data_model)
    # - Use .md for markdown pages (overview, frontend)
    file_path = "./scripts/outputs/frontend_20260212_103037.md"  # or frontend.json

    # Load the page
    result = load_page(
        project_id=project_id,
        name=page_name,
        title=page_title,
        file_path=file_path,
    )

    # Display results
    print(f"\n{'='*50}")
    print(f"✓ Page saved successfully!")
    print(f"{'='*50}")
    print(f"ID:         {result['id']}")
    print(f"Name:       {result['name']}")
    print(f"Title:      {result['title']}")
    print(f"Project ID: {result['project_id']}")

    # Show which field was populated
    if result.get('markdown_content'):
        content_length = len(result['markdown_content'])
        print(f"Type:       Markdown (stored in markdown_content)")
        print(f"Length:     {content_length} characters")
    else:
        print(f"Type:       Structured JSON (stored in content)")
    print(f"{'='*50}")
