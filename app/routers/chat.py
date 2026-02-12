"""Chat API endpoint for sending messages to Claude SDK sessions."""

import logging

from claude_agent_sdk import AssistantMessage, ClaudeAgentOptions, TextBlock, query
from fastapi import APIRouter

from app.dependencies import SessionDep
from app.models.schemas import ChatRequest, ChatResponse
from app.services.sessions import build_chat_prompt

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/{session_id}/chat", response_model=ChatResponse)
async def chat(session: SessionDep, request: ChatRequest):
    """Send a message to a session and get Claude's response.

    This endpoint maintains conversation history across multiple requests.
    Claude SDK will automatically use Read, Glob, and Grep tools to explore
    the codebase as needed.

    Args:
        session: The session from dependency injection
        request: The chat request with user message

    Returns:
        ChatResponse with Claude's response and metadata
    """
    # Build prompt with conversation history
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

        # Update conversation history
        session.message_history.append({"role": "user", "content": request.message})
        session.message_history.append(
            {"role": "assistant", "content": response_text}
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
