"""Sessions API endpoints for managing Claude SDK conversation sessions."""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from app.db import PostgresDatabase, get_db_dependency
from app.dependencies import SessionDep, SessionManagerDep
from app.models.schemas import (
    CreateSessionRequest,
    CreateSessionResponse,
    DeleteSessionResponse,
    ListSessionsResponse,
    SessionDetail,
    UpdateSessionRequest,
    UpdateSessionResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("", response_model=CreateSessionResponse, status_code=201)
async def create_session(
    request: CreateSessionRequest,
    session_manager: SessionManagerDep,
    db: Annotated[PostgresDatabase, Depends(get_db_dependency)],
):
    """Create a new session for a project.

    Args:
        request: The session creation request
        session_manager: The session manager dependency
        db: Database instance

    Returns:
        CreateSessionResponse with session details

    Raises:
        HTTPException: 404 if project not found, 400 if repo_path not set
    """
    try:
        session = await session_manager.create_session(
            request.project_id, db, name=request.name
        )
        return CreateSessionResponse(
            session_id=session.session_id,
            created_at=session.created_at.isoformat(),
            project_id=session.project_id,
            name=session.name,
        )
    except ValueError as e:
        error_msg = str(e)
        if "not found" in error_msg:
            raise HTTPException(status_code=404, detail=error_msg)
        else:
            raise HTTPException(status_code=400, detail=error_msg)


@router.get("", response_model=ListSessionsResponse)
async def list_sessions(
    session_manager: SessionManagerDep,
    project_id: Annotated[str | None, Query()] = None,
):
    """List all sessions, optionally filtered by project.

    Args:
        session_manager: The session manager dependency
        project_id: Optional project ID to filter by

    Returns:
        ListSessionsResponse with sessions and count
    """
    sessions = await session_manager.list_sessions(project_id)
    return ListSessionsResponse(sessions=sessions, count=len(sessions))


@router.get("/{session_id}", response_model=SessionDetail)
async def get_session(session: SessionDep):
    """Get session details including full message history.

    Args:
        session: The session from dependency injection

    Returns:
        SessionDetail with full message history
    """
    return SessionDetail(
        session_id=session.session_id,
        created_at=session.created_at.isoformat(),
        last_accessed=session.last_accessed.isoformat(),
        project_id=session.project_id,
        message_count=len(session.message_history),
        message_history=session.message_history,
        name=session.name,
    )


@router.patch("/{session_id}", response_model=UpdateSessionResponse)
async def update_session(
    session_id: str,
    request: UpdateSessionRequest,
    session_manager: SessionManagerDep,
):
    """Update a session's properties.

    Args:
        session_id: The session ID to update
        request: The update request with fields to modify
        session_manager: The session manager dependency

    Returns:
        UpdateSessionResponse with updated details

    Raises:
        HTTPException: 404 if session not found
    """
    session = await session_manager.update_session(session_id, name=request.name)
    if not session:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")

    return UpdateSessionResponse(
        session_id=session.session_id,
        name=session.name,
        message=f"Session {session_id} updated successfully",
    )


@router.delete("/{session_id}", response_model=DeleteSessionResponse)
async def delete_session(session_id: str, session_manager: SessionManagerDep):
    """Delete a session.

    Args:
        session_id: The session ID to delete
        session_manager: The session manager dependency

    Returns:
        DeleteSessionResponse with success status
    """
    success = await session_manager.delete_session(session_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")

    return DeleteSessionResponse(
        success=True,
        session_id=session_id,
        message=f"Session {session_id} deleted successfully",
    )
