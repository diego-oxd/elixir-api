"""Chat API endpoint for sending messages to Claude SDK sessions."""

import logging
from typing import Annotated

from claude_agent_sdk import AssistantMessage, ClaudeAgentOptions, TextBlock, query
from fastapi import APIRouter, Depends

from app.db import PostgresDatabase, get_db_dependency
from app.dependencies import SessionDep, SessionManagerDep
from app.models.schemas import ChatRequest, ChatResponse
from app.models.session_types import SessionType
from app.services.session_templates import get_template_for_type
from app.services.sessions import build_chat_prompt

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/{session_id}/chat", response_model=ChatResponse)
async def chat(
    session: SessionDep,
    request: ChatRequest,
    session_manager: SessionManagerDep,
    db: Annotated[PostgresDatabase, Depends(get_db_dependency)],
):
    """Send a message to a session and get Claude's response.

    This endpoint maintains conversation history across multiple requests.
    Claude SDK will automatically use Read, Glob, and Grep tools to explore
    the codebase as needed.

    For sessions with special types (e.g., NEW_FEATURE), the first message
    uses a predefined template. Subsequent messages use normal conversation flow.

    Args:
        session: The session from dependency injection
        request: The chat request with user message
        session_manager: The session manager dependency
        db: Database instance

    Returns:
        ChatResponse with Claude's response and metadata
    """
    # Determine which prompt to use based on session type and message history
    is_first_message = len(session.message_history) == 0
    is_special_type = session.session_type != SessionType.GENERAL

    if is_first_message and is_special_type:
        # First message with special type - use template
        logger.info(
            f"Using template for session {session.session_id} "
            f"with type {session.session_type.value}"
        )
        template_func = get_template_for_type(session.session_type)
        prompt = template_func(request.message)
    else:
        # Normal flow - build prompt from conversation history
        prompt = build_chat_prompt(session.message_history, request.message)

    # Configure Claude Agent SDK
    options = ClaudeAgentOptions(
        allowed_tools=["Read", "Glob", "Grep"],
        cwd=session.repo_path,
    )

    # Query the agent
    response_text = ""
    try:
        async for message in query(prompt=prompt, options=options):
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, TextBlock):
                        response_text = block.text

        # Update conversation history and persist to DB
        session.message_history.append({"role": "user", "content": request.message})
        session.message_history.append(
            {"role": "assistant", "content": response_text}
        )
        await session_manager.save_message_history(
            session.session_id, session.message_history, db
        )

        logger.info(
            f"Chat completed for session {session.session_id}. "
            f"Message count: {len(session.message_history)}"
        )

        return ChatResponse(
            session_id=session.session_id,
            response=response_text,
            tool_calls=[],  # Claude Agent SDK handles tools internally
            message_count=len(session.message_history),
        )

    except Exception as e:
        logger.error(f"Error in chat for session {session.session_id}: {e}")
        # On error, don't update history
        raise
