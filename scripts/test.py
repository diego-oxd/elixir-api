import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.db import (
    add_item,
    get_db,
    get_item_by_composite_key,
    get_item_by_id,
    get_items,
    update_item,
    delete_items_by_filter
)

def check_projects():
    with get_db() as db:
        projects = get_items(db, "projects")

        for project in projects:
            print(f"Project ID: {project['_id']}, Name: {project.get('name', 'N/A')}")


def check_pages():
    with get_db() as db:
        pages = get_items(db, "pages")

        for page in pages:
            print(page['_id'], page.get('name', 'N/A'), page.get('project_id', 'N/A'))


def delete_pages_by_project(project_id: str):
    """Delete all pages that belong to a specific project."""
    with get_db() as db:
        deleted_count = delete_items_by_filter(db, "pages", {"project_id": project_id})
        print(f"Deleted {deleted_count} pages for project_id: {project_id}")
        return deleted_count


if __name__ == "__main__":
    # check_projects()
    # project_id = "a4042b78-d583-41c7-b843-3460c5b5f2a3"
    # delete_pages_by_project(project_id)
    check_pages()