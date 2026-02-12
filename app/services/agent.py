import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Type

from claude_agent_sdk import query, ClaudeAgentOptions, AssistantMessage, TextBlock, ResultMessage
from pydantic import BaseModel

# Set up logging
logger = logging.getLogger(__name__)

# Create logs directory for audit trails
LOGS_DIR = Path("logs/agent_responses")
LOGS_DIR.mkdir(parents=True, exist_ok=True)


async def query_codebase(user_query: str, repo_path: str) -> str:
    """
    Query a codebase using Claude Agent SDK.

    Args:
        user_query: The user's question about the code
        repo_path: Absolute path to the repository

    Returns:
        Claude's text response
    """
    options = ClaudeAgentOptions(
        allowed_tools=["Read", "Glob", "Grep"],
        cwd=repo_path,
    )

    last_text = ""
    async for message in query(prompt=user_query, options=options):
        if isinstance(message, AssistantMessage):
            for block in message.content:
                if isinstance(block, TextBlock):
                    last_text = block.text

    return last_text


async def query_codebase_markdown(
    user_query: str,
    repo_path: str,
    system_prompt: str | None = None,
) -> str:
    """
    Query a codebase and return plain markdown documentation.

    This function is optimized for generating markdown documentation
    without structured output constraints. The response is pure markdown text
    ready for storage and rendering.

    Args:
        user_query: The documentation prompt/question
        repo_path: Absolute path to the repository
        system_prompt: Optional system prompt (defaults to markdown-focused prompt)

    Returns:
        Plain markdown text

    Raises:
        ValueError: If no text response is received
    """
    if system_prompt is None:
        system_prompt = (
            "You are a technical documentation expert analyzing codebases. "
            "Generate clear, well-structured markdown documentation. "
            "Return ONLY markdown - do not wrap in JSON or any other format. "
            "Use proper markdown syntax and avoid characters that cause parsing issues."
        )

    options = ClaudeAgentOptions(
        allowed_tools=["Read", "Glob", "Grep"],
        cwd=repo_path,
        system_prompt=system_prompt,
    )

    logger.info(f"Starting markdown documentation generation for {repo_path}")

    last_text = ""
    async for message in query(prompt=user_query, options=options):
        if isinstance(message, AssistantMessage):
            for block in message.content:
                if isinstance(block, TextBlock):
                    last_text = block.text

    if not last_text:
        raise ValueError("No markdown content received from agent")

    logger.info(f"Successfully generated markdown documentation ({len(last_text)} chars)")
    return last_text


async def query_codebase_json(
    user_query: str,
    repo_path: str,
    response_model: Type[BaseModel],
    system_prompt: str | None = None,
) -> BaseModel:
    """
    Query a codebase and enforce a specific Pydantic schema using structured outputs.

    This uses Claude's output_format parameter for constrained decoding,
    which guarantees the response will match your schema.

    All responses (successful and failed) are logged to logs/agent_responses/
    for auditing and debugging.

    Args:
        user_query: The user's question about the code
        repo_path: Absolute path to the repository
        response_model: Pydantic model to enforce
        system_prompt: Optional system prompt (defaults to a JSON-focused prompt)

    Returns:
        Validated Pydantic model instance

    Raises:
        ValueError: If response isn't valid JSON with details and log path
        ValidationError: If JSON doesn't match Pydantic schema with details
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    log_file = LOGS_DIR / f"response_{timestamp}.json"

    if system_prompt is None:
        system_prompt = (
            "You are a technical architect analyzing codebases. "
            "Respond with valid JSON matching the requested schema."
        )

    # Convert Pydantic model to JSON schema
    json_schema = response_model.model_json_schema()

    # Ensure additionalProperties is false for all objects (required by Claude)
    def add_additional_properties_false(schema):
        if isinstance(schema, dict):
            if schema.get("type") == "object":
                schema["additionalProperties"] = False
            for value in schema.values():
                if isinstance(value, dict):
                    add_additional_properties_false(value)
                elif isinstance(value, list):
                    for item in value:
                        if isinstance(item, dict):
                            add_additional_properties_false(item)

    add_additional_properties_false(json_schema)

    logger.info(f"Starting codebase query for {repo_path}")
    logger.info(f"Schema: {response_model.__name__}")

    # Configure Claude with structured outputs
    options = ClaudeAgentOptions(
        allowed_tools=["Read", "Glob", "Grep"],
        cwd=repo_path,
        system_prompt=system_prompt,
        output_format={
            "type": "json_schema",
            "schema": json_schema,
        },
    )

    last_text = ""
    stop_reason = None
    structured_output = None
    result_subtype = None

    try:
        async for message in query(prompt=user_query, options=options):
            # Capture structured output from ResultMessage
            if isinstance(message, ResultMessage):
                structured_output = message.structured_output
                result_subtype = message.subtype
                if hasattr(message, "stop_reason"):
                    stop_reason = message.stop_reason

            # Also capture text for debugging/logging
            if isinstance(message, AssistantMessage):
                if hasattr(message, "stop_reason"):
                    stop_reason = message.stop_reason
                for block in message.content:
                    if isinstance(block, TextBlock):
                        last_text = block.text

        # Log the complete response
        log_data = {
            "timestamp": timestamp,
            "repo_path": repo_path,
            "schema": response_model.__name__,
            "query_length": len(user_query),
            "response_length": len(last_text) if last_text else (len(json.dumps(structured_output)) if structured_output else 0),
            "stop_reason": stop_reason,
            "result_subtype": result_subtype,
            "raw_response": last_text if last_text else (json.dumps(structured_output) if structured_output else ""),
            "has_structured_output": structured_output is not None,
            "success": False,  # Will update if successful
        }

        # Check for structured output errors
        if result_subtype == "error_max_structured_output_retries":
            log_data["error"] = "Agent hit max retries trying to produce valid output"
            log_file.write_text(json.dumps(log_data, indent=2))
            raise ValueError(
                f"Agent could not produce valid output after multiple attempts. "
                f"This usually means: (1) schema too complex, (2) task is ambiguous, "
                f"or (3) required fields cannot be determined. Check log: {log_file}"
            )

        # Check if we got structured output
        if structured_output is None:
            log_data["error"] = "No structured output received from agent"
            log_file.write_text(json.dumps(log_data, indent=2))
            raise ValueError(
                f"Agent did not return structured output. "
                f"Result subtype: {result_subtype}. "
                f"Check log: {log_file}"
            )

        # Validate with Pydantic (structured_output is already validated by SDK, but we double-check)
        validated = response_model.model_validate(structured_output)

        # Mark as successful
        log_data["success"] = True
        log_file.write_text(json.dumps(log_data, indent=2))

        logger.info(f"Successfully received structured output. Log: {log_file}")
        return validated

    except Exception as e:
        # Only log if we haven't already
        if "error" not in log_data:
            log_data["error"] = str(e)
            log_data["error_type"] = type(e).__name__
        log_file.write_text(json.dumps(log_data, indent=2))

        logger.error(f"Error processing response: {e}. Log: {log_file}")
        raise
