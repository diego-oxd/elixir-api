"""Session management for Claude SDK conversations."""

import asyncio
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from app.db import PostgresDatabase, get_item_by_id
from app.models.schemas import SessionInfo

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

    def to_info(self) -> SessionInfo:
        """Convert to SessionInfo model for API responses."""
        return SessionInfo(
            session_id=self.session_id,
            created_at=self.created_at.isoformat(),
            last_accessed=self.last_accessed.isoformat(),
            project_id=self.project_id,
            message_count=len(self.message_history),
            name=self.name,
        )


class SessionManager:
    """Manages active sessions with automatic cleanup."""

    def __init__(
        self, default_timeout_minutes: int = 30, cleanup_interval_seconds: int = 60
    ):
        self._sessions: dict[str, APISession] = {}
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
        self, project_id: str, db: PostgresDatabase, name: str | None = None
    ) -> APISession:
        """Create a new session for a project.

        Args:
            project_id: The project ID to create a session for
            db: Database instance to fetch project info
            name: Optional name for the session

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

        # Create session
        session_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)

        session = APISession(
            session_id=session_id,
            created_at=now,
            last_accessed=now,
            project_id=project_id,
            repo_path=repo_path,
            message_history=[],
            name=name,
        )

        self._sessions[session_id] = session
        logger.info(f"Created session {session_id} for project {project_id}")

        return session

    async def get_session(self, session_id: str) -> APISession | None:
        """Get a session by ID and update last_accessed.

        Args:
            session_id: The session ID to retrieve

        Returns:
            The APISession if found, None otherwise
        """
        session = self._sessions.get(session_id)
        if session:
            session.last_accessed = datetime.now(timezone.utc)
        return session

    async def update_session(
        self, session_id: str, name: str | None = None
    ) -> APISession | None:
        """Update a session's properties.

        Args:
            session_id: The session ID to update
            name: New name for the session (if provided)

        Returns:
            The updated APISession if found, None otherwise
        """
        session = self._sessions.get(session_id)
        if not session:
            return None

        if name is not None:
            session.name = name

        session.last_accessed = datetime.now(timezone.utc)
        logger.info(f"Updated session {session_id}")
        return session

    async def delete_session(self, session_id: str) -> bool:
        """Delete a session.

        Args:
            session_id: The session ID to delete

        Returns:
            True if session was found and deleted, False otherwise
        """
        if session_id in self._sessions:
            del self._sessions[session_id]
            logger.info(f"Deleted session {session_id}")
            return True
        return False

    async def list_sessions(
        self, project_id: str | None = None
    ) -> list[SessionInfo]:
        """List all sessions, optionally filtered by project.

        Args:
            project_id: Optional project ID to filter by

        Returns:
            List of SessionInfo objects
        """
        sessions = self._sessions.values()
        if project_id:
            sessions = [s for s in sessions if s.project_id == project_id]

        return [session.to_info() for session in sessions]

    async def cleanup_expired(self) -> int:
        """Remove sessions that haven't been accessed recently.

        Returns:
            Number of sessions removed
        """
        now = datetime.now(timezone.utc)
        timeout_delta = timedelta(minutes=self._timeout_minutes)

        expired_ids = [
            session_id
            for session_id, session in self._sessions.items()
            if now - session.last_accessed > timeout_delta
        ]

        for session_id in expired_ids:
            del self._sessions[session_id]

        return len(expired_ids)

    async def close_all_sessions(self) -> None:
        """Close all sessions. Called on shutdown."""
        count = len(self._sessions)
        self._sessions.clear()
        logger.info(f"Closed {count} sessions")


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
