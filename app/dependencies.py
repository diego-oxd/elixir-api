"""FastAPI dependencies for session management."""

from typing import Annotated

from fastapi import Depends, HTTPException, Path

from app.services.sessions import APISession, SessionManager

_session_manager: SessionManager | None = None


def set_session_manager(manager: SessionManager) -> None:
    """Set the global session manager instance.

    Args:
        manager: The SessionManager instance to use
    """
    global _session_manager
    _session_manager = manager


def get_session_manager() -> SessionManager:
    """Get the global session manager instance.

    Returns:
        The SessionManager instance

    Raises:
        RuntimeError: If session manager not initialized
    """
    if _session_manager is None:
        raise RuntimeError("Session manager not initialized")
    return _session_manager


async def get_session(
    session_id: Annotated[str, Path()],
    session_manager: Annotated[SessionManager, Depends(get_session_manager)],
) -> APISession:
    """Get a session by ID or raise 404.

    Args:
        session_id: The session ID from the path
        session_manager: The session manager dependency

    Returns:
        The APISession

    Raises:
        HTTPException: 404 if session not found
    """
    session = await session_manager.get_session(session_id)
    if session is None:
        raise HTTPException(
            status_code=404, detail=f"Session {session_id} not found"
        )
    return session


# Type aliases for cleaner annotations
SessionManagerDep = Annotated[SessionManager, Depends(get_session_manager)]
SessionDep = Annotated[APISession, Depends(get_session)]
