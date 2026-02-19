"""Session management for Claude SDK conversations."""

import asyncio
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from psycopg2.extras import Json

from app.db import PostgresDatabase, get_db, get_item_by_id
from app.models.schemas import SessionInfo
from app.models.session_types import SessionType

logger = logging.getLogger(__name__)


@dataclass
class APISession:
    """Represents an active session with conversation history."""

    session_id: str
    created_at: datetime
    last_accessed: datetime
    project_id: str
    repo_path: str
    message_history: list[dict] = field(default_factory=list)
    name: str | None = None
    session_type: SessionType = SessionType.GENERAL

    def to_info(self) -> SessionInfo:
        """Convert to SessionInfo model for API responses."""
        return SessionInfo(
            session_id=self.session_id,
            created_at=self.created_at.isoformat(),
            last_accessed=self.last_accessed.isoformat(),
            project_id=self.project_id,
            message_count=len(self.message_history),
            name=self.name,
            session_type=self.session_type.value,
        )


def _row_to_session(row: dict, repo_path: str) -> APISession:
    """Convert a DB row to an APISession."""
    created_at = row["created_at"]
    last_accessed = row["last_accessed"]

    # Ensure timezone-aware datetimes
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    if last_accessed.tzinfo is None:
        last_accessed = last_accessed.replace(tzinfo=timezone.utc)

    return APISession(
        session_id=str(row["id"]),
        created_at=created_at,
        last_accessed=last_accessed,
        project_id=str(row["project_id"]),
        repo_path=repo_path,
        message_history=row.get("message_history") or [],
        name=row.get("name"),
        session_type=SessionType(row.get("session_type", "general")),
    )


class SessionManager:
    """Manages sessions persisted in PostgreSQL."""

    def __init__(
        self, default_timeout_minutes: int = 30, cleanup_interval_seconds: int = 60
    ):
        self._timeout_minutes = default_timeout_minutes
        self._cleanup_interval = cleanup_interval_seconds
        self._cleanup_task: asyncio.Task | None = None
        self._running = False

    def start_cleanup_task(self) -> None:
        """Start the background cleanup task."""
        if self._cleanup_task is None or self._cleanup_task.done():
            self._running = True
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())
            logger.info("Session cleanup task started")

    async def stop_cleanup_task(self) -> None:
        """Stop the background cleanup task."""
        self._running = False
        if self._cleanup_task and not self._cleanup_task.done():
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
            logger.info("Session cleanup task stopped")

    async def _cleanup_loop(self) -> None:
        """Background task that periodically cleans up expired sessions."""
        while self._running:
            try:
                await asyncio.sleep(self._cleanup_interval)
                count = await self.cleanup_expired()
                if count > 0:
                    logger.info(f"Cleaned up {count} expired sessions")
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in cleanup loop: {e}")

    async def create_session(
        self,
        project_id: str,
        db: PostgresDatabase,
        name: str | None = None,
        session_type: SessionType | None = None,
    ) -> APISession:
        """Create a new session for a project.

        Args:
            project_id: The project ID to create a session for
            db: Database instance to fetch project info
            name: Optional name for the session
            session_type: Type of session (defaults to GENERAL)

        Returns:
            The created APISession

        Raises:
            ValueError: If project not found or repo_path not set
        """
        # Fetch project from database
        project = get_item_by_id(db, "projects", project_id)
        if project is None:
            raise ValueError(f"Project {project_id} not found")

        repo_path = project.get("repo_path")
        if not repo_path:
            raise ValueError(
                f"Project {project_id} does not have repo_path set. "
                "Please add a codebase first."
            )

        # Create session in DB
        session_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)
        effective_type = session_type or SessionType.GENERAL

        with db.cursor() as cur:
            cur.execute(
                """
                INSERT INTO sessions (id, project_id, name, created_at, last_accessed, message_history, session_type)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING *
                """,
                (session_id, project_id, name, now, now, Json([]), effective_type.value),
            )
            row = cur.fetchone()

        session = _row_to_session(row, repo_path)
        logger.info(
            f"Created session {session_id} for project {project_id} "
            f"with type {session.session_type.value}"
        )

        return session

    async def get_session(
        self, session_id: str, db: PostgresDatabase
    ) -> APISession | None:
        """Get a session by ID and update last_accessed.

        Args:
            session_id: The session ID to retrieve
            db: Database instance

        Returns:
            The APISession if found, None otherwise
        """
        with db.cursor() as cur:
            # Fetch session joined with project to get repo_path
            cur.execute(
                """
                SELECT s.*, p.repo_path
                FROM sessions s
                JOIN projects p ON s.project_id = p.id
                WHERE s.id = %s
                """,
                (session_id,),
            )
            row = cur.fetchone()

            if row is None:
                return None

            # Update last_accessed
            now = datetime.now(timezone.utc)
            cur.execute(
                "UPDATE sessions SET last_accessed = %s WHERE id = %s",
                (now, session_id),
            )

        repo_path = row["repo_path"]
        session = _row_to_session(row, repo_path)
        session.last_accessed = now
        return session

    async def update_session(
        self, session_id: str, db: PostgresDatabase, name: str | None = None
    ) -> APISession | None:
        """Update a session's properties.

        Args:
            session_id: The session ID to update
            db: Database instance
            name: New name for the session (if provided)

        Returns:
            The updated APISession if found, None otherwise
        """
        with db.cursor() as cur:
            # Check session exists and get repo_path
            cur.execute(
                """
                SELECT s.*, p.repo_path
                FROM sessions s
                JOIN projects p ON s.project_id = p.id
                WHERE s.id = %s
                """,
                (session_id,),
            )
            row = cur.fetchone()

            if row is None:
                return None

            # Update fields
            now = datetime.now(timezone.utc)
            if name is not None:
                cur.execute(
                    "UPDATE sessions SET name = %s, last_accessed = %s WHERE id = %s",
                    (name, now, session_id),
                )
            else:
                cur.execute(
                    "UPDATE sessions SET last_accessed = %s WHERE id = %s",
                    (now, session_id),
                )

        repo_path = row["repo_path"]
        session = _row_to_session(row, repo_path)
        if name is not None:
            session.name = name
        session.last_accessed = now
        logger.info(f"Updated session {session_id}")
        return session

    async def delete_session(self, session_id: str, db: PostgresDatabase) -> bool:
        """Delete a session.

        Args:
            session_id: The session ID to delete
            db: Database instance

        Returns:
            True if session was found and deleted, False otherwise
        """
        with db.cursor() as cur:
            cur.execute("DELETE FROM sessions WHERE id = %s", (session_id,))
            deleted = cur.rowcount > 0

        if deleted:
            logger.info(f"Deleted session {session_id}")
        return deleted

    async def list_sessions(
        self, db: PostgresDatabase, project_id: str | None = None
    ) -> list[SessionInfo]:
        """List all sessions, optionally filtered by project.

        Args:
            db: Database instance
            project_id: Optional project ID to filter by

        Returns:
            List of SessionInfo objects
        """
        with db.cursor() as cur:
            if project_id:
                cur.execute(
                    """
                    SELECT s.*, p.repo_path
                    FROM sessions s
                    JOIN projects p ON s.project_id = p.id
                    WHERE s.project_id = %s
                    ORDER BY s.last_accessed DESC
                    """,
                    (project_id,),
                )
            else:
                cur.execute(
                    """
                    SELECT s.*, p.repo_path
                    FROM sessions s
                    JOIN projects p ON s.project_id = p.id
                    ORDER BY s.last_accessed DESC
                    """
                )
            rows = cur.fetchall()

        return [_row_to_session(row, row["repo_path"]).to_info() for row in rows]

    async def save_message_history(
        self, session_id: str, message_history: list[dict], db: PostgresDatabase
    ) -> None:
        """Save updated message history to the database.

        Args:
            session_id: The session ID to update
            message_history: The full message history to save
            db: Database instance
        """
        now = datetime.now(timezone.utc)
        with db.cursor() as cur:
            cur.execute(
                "UPDATE sessions SET message_history = %s, last_accessed = %s WHERE id = %s",
                (Json(message_history), now, session_id),
            )

    async def cleanup_expired(self) -> int:
        """Remove sessions that haven't been accessed recently.

        Returns:
            Number of sessions removed
        """
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=self._timeout_minutes)

        with get_db() as db:
            with db.cursor() as cur:
                cur.execute(
                    "DELETE FROM sessions WHERE last_accessed < %s",
                    (cutoff,),
                )
                count = cur.rowcount

        return count


# Helper functions for building prompts
def format_message_history(messages: list[dict]) -> str:
    """Format conversation history into readable text for prompt context.

    Args:
        messages: List of message dicts with 'role' and 'content' keys

    Returns:
        Formatted string with conversation history
    """
    formatted = []
    for msg in messages:
        role = msg["role"].capitalize()
        content = msg["content"]
        formatted.append(f"{role}: {content}")
    return "\n\n".join(formatted)


def build_chat_prompt(history: list[dict], new_message: str) -> str:
    """Build prompt with conversation history and new message.

    Args:
        history: Previous conversation messages
        new_message: The new user message

    Returns:
        Complete prompt with context and new message
    """
    if not history:
        return new_message

    history_text = format_message_history(history)
    return f"""Previous conversation:
{history_text}

User's new question: {new_message}

Please respond to the user's new question, using the previous conversation context if relevant."""
