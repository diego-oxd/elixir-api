"""Migration script to add name column to sessions table."""

import sys
import os

# Add parent directory to path so we can import app modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db import get_db


def add_session_name_column():
    """Add name column to sessions table."""
    with get_db() as db:
        with db.cursor() as cur:
            # Check if column already exists
            cur.execute("""
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name='sessions' AND column_name='name'
            """)

            if cur.fetchone():
                print("✓ Column 'name' already exists in sessions table")
                return

            # Add the column
            cur.execute("ALTER TABLE sessions ADD COLUMN name TEXT")
            print("✓ Successfully added 'name' column to sessions table")


if __name__ == "__main__":
    try:
        add_session_name_column()
    except Exception as e:
        print(f"✗ Error: {e}")
        sys.exit(1)
