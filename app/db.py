import os
import uuid
from contextlib import contextmanager
from typing import Any, Generator

import psycopg2
from psycopg2.extras import Json, RealDictCursor
from psycopg2.pool import SimpleConnectionPool


# ============================================================================
# Result Objects (MongoDB-compatible)
# ============================================================================


class InsertResult:
    """Mimics pymongo's InsertOneResult."""

    def __init__(self, inserted_id: str):
        self.inserted_id = inserted_id


class InsertManyResult:
    """Mimics pymongo's InsertManyResult."""

    def __init__(self, inserted_ids: list[str]):
        self.inserted_ids = inserted_ids


class UpdateResult:
    """Mimics pymongo's UpdateResult."""

    def __init__(self, modified_count: int):
        self.modified_count = modified_count


class DeleteResult:
    """Mimics pymongo's DeleteResult."""

    def __init__(self, deleted_count: int):
        self.deleted_count = deleted_count


# ============================================================================
# Database Wrapper
# ============================================================================


class PostgresDatabase:
    """Wrapper around psycopg2 connection to provide collection-like interface."""

    def __init__(self, conn):
        self.conn = conn

    def cursor(self, **kwargs):
        """Get a cursor with RealDictCursor by default."""
        return self.conn.cursor(cursor_factory=RealDictCursor, **kwargs)


# ============================================================================
# Connection Pool
# ============================================================================

_pool: SimpleConnectionPool | None = None


def get_pool() -> SimpleConnectionPool:
    """Get or create connection pool."""
    global _pool
    if _pool is None:
        uri = os.getenv(
            "DATABASE_URL",
            "postgresql://app_user:app_password@localhost:5432/knowledge_extraction",
        )
        _pool = SimpleConnectionPool(1, 20, uri)
    return _pool


def close_pool():
    """Close the connection pool."""
    global _pool
    if _pool is not None:
        _pool.closeall()
        _pool = None


def get_client():
    """Get connection pool (for compatibility with old interface)."""
    return get_pool()


@contextmanager
def get_db(db_name: str | None = None) -> Generator[PostgresDatabase, None, None]:
    """Context manager for database operations."""
    pool = get_pool()
    conn = pool.getconn()
    try:
        db = PostgresDatabase(conn)
        yield db
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        pool.putconn(conn)


def get_db_dependency() -> Generator[PostgresDatabase, None, None]:
    """Get database instance for FastAPI dependency injection.

    Each request gets its own connection from the pool.
    """
    with get_db() as db:
        yield db


# ============================================================================
# Table Schema Definitions
# ============================================================================

# Define which columns belong to each table
TABLE_COLUMNS = {
    "projects": ["id", "name", "description", "repo_path", "repo_url"],
    "pages": ["id", "project_id", "name", "title", "content", "markdown_content"],
    "code_samples": ["id", "project_id", "title", "language", "description", "code_string"],
    "doc_pages": ["id", "project_id", "title", "content"],
    "sessions": ["id", "project_id", "name", "created_at", "last_accessed", "message_history"],
}


# ============================================================================
# Helper Functions
# ============================================================================


def _row_to_dict(row: dict | None, collection_name: str) -> dict | None:
    """Convert DB row to MongoDB-style dict with _id."""
    if row is None:
        return None

    result = dict(row)
    # Convert id to _id for API compatibility
    if "id" in result:
        result["_id"] = result.pop("id")
    # Remove internal timestamp fields
    result.pop("created_at", None)
    result.pop("updated_at", None)
    return result


def _build_where_clause(filters: dict) -> tuple[str, list[Any]]:
    """
    Build SQL WHERE clause from MongoDB-style filters.

    Supports:
    - {"field": value} -> WHERE field = value
    - {"field": {"$in": [...]}} -> WHERE field = ANY(ARRAY[...])
    - {"field": {"$ne": value}} -> WHERE field != value
    - Multiple conditions are combined with AND

    Returns:
        Tuple of (where_clause, params)
    """
    if not filters:
        return "", []

    conditions = []
    params = []
    param_counter = 1

    for key, value in filters.items():
        if isinstance(value, dict):
            # Handle MongoDB operators
            if "$in" in value:
                conditions.append(f"{key} = ANY(%s)")
                params.append(list(value["$in"]))
            elif "$ne" in value:
                conditions.append(f"{key} != %s")
                params.append(value["$ne"])
            elif "$gt" in value:
                conditions.append(f"{key} > %s")
                params.append(value["$gt"])
            elif "$gte" in value:
                conditions.append(f"{key} >= %s")
                params.append(value["$gte"])
            elif "$lt" in value:
                conditions.append(f"{key} < %s")
                params.append(value["$lt"])
            elif "$lte" in value:
                conditions.append(f"{key} <= %s")
                params.append(value["$lte"])
            else:
                raise ValueError(f"Unsupported operator in filter: {value}")
        else:
            # Simple equality
            conditions.append(f"{key} = %s")
            params.append(value)

    where_clause = " AND ".join(conditions)
    return where_clause, params


# ============================================================================
# CRUD Operations
# ============================================================================


def create_collection(db: PostgresDatabase, collection_name: str):
    """Create a collection (table) in the database.

    Note: Tables are created via init_db.sql, so this is a no-op for compatibility.
    """
    pass


def add_item(db: PostgresDatabase, collection_name: str, item: dict) -> InsertResult:
    """Add a single item to a collection."""
    # Generate UUID if not provided
    item_id = item.get("id") or item.get("_id") or str(uuid.uuid4())

    # Get table columns
    columns = TABLE_COLUMNS.get(collection_name, [])
    if not columns:
        raise ValueError(f"Unknown collection: {collection_name}")

    # Prepare data for insertion
    insert_data = {"id": item_id}

    for col in columns:
        if col == "id":
            continue
        if col in item:
            value = item[col]
            # Special handling for pages.content (JSONB)
            if collection_name == "pages" and col == "content":
                insert_data[col] = Json(value)
            else:
                insert_data[col] = value

    # Build INSERT query
    cols = list(insert_data.keys())
    placeholders = ["%s"] * len(cols)
    query = f"""
        INSERT INTO {collection_name} ({', '.join(cols)})
        VALUES ({', '.join(placeholders)})
        RETURNING id
    """

    with db.cursor() as cur:
        cur.execute(query, list(insert_data.values()))
        result = cur.fetchone()
        return InsertResult(inserted_id=result["id"])


def add_items(
    db: PostgresDatabase, collection_name: str, items: list[dict]
) -> InsertManyResult:
    """Add multiple items to a collection."""
    inserted_ids = []
    for item in items:
        result = add_item(db, collection_name, item)
        inserted_ids.append(result.inserted_id)
    return InsertManyResult(inserted_ids=inserted_ids)


def get_items(db: PostgresDatabase, collection_name: str) -> list[dict]:
    """Get all items from a collection."""
    query = f"SELECT * FROM {collection_name}"

    with db.cursor() as cur:
        cur.execute(query)
        rows = cur.fetchall()
        return [_row_to_dict(row, collection_name) for row in rows]


def get_item_by_id(
    db: PostgresDatabase, collection_name: str, item_id: str | uuid.UUID
) -> dict | None:
    """Get a single item by its _id."""
    # Handle UUID or string
    if not isinstance(item_id, str):
        item_id = str(item_id)

    query = f"SELECT * FROM {collection_name} WHERE id = %s"

    with db.cursor() as cur:
        cur.execute(query, (item_id,))
        row = cur.fetchone()
        return _row_to_dict(row, collection_name)


def get_item_by_composite_key(
    db: PostgresDatabase, collection_name: str, project_id: str, name: str
) -> dict | None:
    """Get a single item by project_id and name (assumed unique together)."""
    query = f"SELECT * FROM {collection_name} WHERE project_id = %s AND name = %s"

    with db.cursor() as cur:
        cur.execute(query, (project_id, name))
        row = cur.fetchone()
        return _row_to_dict(row, collection_name)


def get_items_by_filter(
    db: PostgresDatabase, collection_name: str, filters: dict
) -> list[dict]:
    """Get all items matching the given filters."""
    where_clause, params = _build_where_clause(filters)

    if where_clause:
        query = f"SELECT * FROM {collection_name} WHERE {where_clause}"
    else:
        query = f"SELECT * FROM {collection_name}"

    with db.cursor() as cur:
        cur.execute(query, params)
        rows = cur.fetchall()
        return [_row_to_dict(row, collection_name) for row in rows]


def update_item(
    db: PostgresDatabase, collection_name: str, item_id: str | uuid.UUID, updates: dict
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

    if not isinstance(item_id, str):
        item_id = str(item_id)

    # Build SET clause
    set_parts = []
    params = []
    for key, value in updates.items():
        # Special handling for pages.content (JSONB)
        if collection_name == "pages" and key == "content":
            set_parts.append(f"{key} = %s")
            params.append(Json(value))
        else:
            set_parts.append(f"{key} = %s")
            params.append(value)

    params.append(item_id)  # For WHERE clause

    query = f"""
        UPDATE {collection_name}
        SET {', '.join(set_parts)}
        WHERE id = %s
    """

    with db.cursor() as cur:
        cur.execute(query, params)
        return cur.rowcount > 0


def delete_item(
    db: PostgresDatabase, collection_name: str, item_id: str | uuid.UUID
) -> bool:
    """Delete a single item by its _id.

    Args:
        db: The database instance.
        collection_name: Name of the collection.
        item_id: The _id of the item to delete.

    Returns:
        True if an item was deleted, False otherwise.
    """
    if not isinstance(item_id, str):
        item_id = str(item_id)

    query = f"DELETE FROM {collection_name} WHERE id = %s"

    with db.cursor() as cur:
        cur.execute(query, (item_id,))
        return cur.rowcount > 0


def delete_items_by_filter(
    db: PostgresDatabase, collection_name: str, filters: dict
) -> int:
    """Delete all items matching the given filters.

    Args:
        db: The database instance.
        collection_name: Name of the collection.
        filters: Dictionary of field:value pairs to filter items.

    Returns:
        Number of items deleted.
    """
    where_clause, params = _build_where_clause(filters)

    if not where_clause:
        raise ValueError("Filters required for delete_items_by_filter")

    query = f"DELETE FROM {collection_name} WHERE {where_clause}"

    with db.cursor() as cur:
        cur.execute(query, params)
        return cur.rowcount


# ============================================================================
# Test/Debug
# ============================================================================

if __name__ == "__main__":
    with get_db() as db:
        items = get_items(db, "projects")
        print(items)
