import os
from contextlib import contextmanager
from typing import Generator

from bson import ObjectId
from pymongo import MongoClient
from pymongo.database import Database


def get_client() -> MongoClient:
    """Create a new MongoDB client."""
    uri = os.getenv("MONGODB_URI", "mongodb://ferret:ferret@localhost:27017/?authSource=admin")
    return MongoClient(uri)


@contextmanager
def get_db(db_name: str | None = None) -> Generator[Database, None, None]:
    """Context manager for database operations."""
    client = get_client()
    try:
        name = db_name or os.getenv("MONGODB_DATABASE", "app")
        yield client[name]
    finally:
        client.close()


def create_collection(db: Database, collection_name: str):
    """Create a collection in the database."""
    return db.create_collection(collection_name)


def add_item(db: Database, collection_name: str, item: dict):
    """Add a single item to a collection."""
    return db[collection_name].insert_one(item)


def add_items(db: Database, collection_name: str, items: list[dict]):
    """Add multiple items to a collection."""
    return db[collection_name].insert_many(items)


def get_items(db: Database, collection_name: str) -> list[dict]:
    """Get all items from a collection."""
    return list(db[collection_name].find())


def get_item_by_id(db: Database, collection_name: str, item_id: str | ObjectId) -> dict | None:
    """Get a single item by its _id."""
    if isinstance(item_id, str):
        item_id = ObjectId(item_id)
    return db[collection_name].find_one({"_id": item_id})


def get_item_by_composite_key(
    db: Database, collection_name: str, project_id: str, name: str
) -> dict | None:
    """Get a single item by project_id and name (assumed unique together)."""
    return db[collection_name].find_one({"project_id": project_id, "name": name})


def get_items_by_filter(
    db: Database, collection_name: str, filters: dict
) -> list[dict]:
    """Get all items matching the given key-value pairs."""
    return list(db[collection_name].find(filters))


def update_item(
    db: Database, collection_name: str, item_id: str | ObjectId, updates: dict
) -> bool:
    """Update a single item by its _id.

    Args:
        db: The database instance.
        collection_name: Name of the collection.
        item_id: The _id of the item to update.
        updates: Dictionary of field:value pairs to update.

    Returns:
        True if an item was updated, False otherwise.

    Raises:
        ValueError: If any key in updates starts with '$' (prevents operator injection).
    """
    if any(key.startswith("$") for key in updates):
        raise ValueError("Update keys cannot start with '$'")

    if isinstance(item_id, str):
        item_id = ObjectId(item_id)

    result = db[collection_name].update_one({"_id": item_id}, {"$set": updates})
    return result.modified_count > 0


def delete_item(db: Database, collection_name: str, item_id: str | ObjectId) -> bool:
    """Delete a single item by its _id.

    Args:
        db: The database instance.
        collection_name: Name of the collection.
        item_id: The _id of the item to delete.

    Returns:
        True if an item was deleted, False otherwise.
    """
    if isinstance(item_id, str):
        item_id = ObjectId(item_id)

    result = db[collection_name].delete_one({"_id": item_id})
    return result.deleted_count > 0


def delete_items_by_filter(
    db: Database, collection_name: str, filters: dict
) -> int:
    """Delete all items matching the given filters.

    Args:
        db: The database instance.
        collection_name: Name of the collection.
        filters: Dictionary of field:value pairs to filter items.

    Returns:
        Number of items deleted.
    """
    result = db[collection_name].delete_many(filters)
    return result.deleted_count


if __name__ == "__main__":
    with get_db("elixir") as db:
        items = get_items(db, "projects")
        print(items)
