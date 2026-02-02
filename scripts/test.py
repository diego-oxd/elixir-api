from app.db import (
    add_item,
    get_db,
    get_item_by_composite_key,
    get_item_by_id,
    update_item,
)

def check_projects():
    with get_db() as db:
        projects = list(db["projects"].find({}))

        for project in projects:
            print(f"Project ID: {project['_id']}, Name: {project.get('name', 'N/A')}")


if __name__ == "__main__":
    check_projects()