import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Type

from claude_agent_sdk import query, ClaudeAgentOptions, AssistantMessage, TextBlock
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
    all_messages = []

    try:
        async for message in query(prompt=user_query, options=options):
            all_messages.append(message)
            if isinstance(message, AssistantMessage):
                # Check for stop reason
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
            "response_length": len(last_text),
            "stop_reason": stop_reason,
            "raw_response": last_text,
            "success": False,  # Will update if successful
        }

        # Check if response is empty
        if not last_text.strip():
            log_data["error"] = "Empty response from agent"
            log_data["stop_reason"] = stop_reason
            log_file.write_text(json.dumps(log_data, indent=2))
            raise ValueError(
                f"Agent returned empty response. Stop reason: {stop_reason}. "
                f"This may indicate: (1) max_tokens too low, (2) model refusal, "
                f"or (3) schema too complex. Check log: {log_file}"
            )

        # Parse JSON and validate with Pydantic
        parsed = json.loads(last_text.strip())
        validated = response_model.model_validate(parsed)

        # Mark as successful
        log_data["success"] = True
        log_file.write_text(json.dumps(log_data, indent=2))

        logger.info(f"Successfully parsed response. Log: {log_file}")
        return validated

    except json.JSONDecodeError as e:
        log_data["error"] = f"JSON decode error: {str(e)}"
        log_data["error_type"] = "JSONDecodeError"
        log_file.write_text(json.dumps(log_data, indent=2))

        logger.error(f"JSON decode failed. Log: {log_file}")
        raise ValueError(
            f"Agent returned invalid JSON: {str(e)}. "
            f"Stop reason: {stop_reason}. "
            f"Response length: {len(last_text)} chars. "
            f"Check log: {log_file}"
        ) from e

    except Exception as e:
        log_data["error"] = str(e)
        log_data["error_type"] = type(e).__name__
        log_file.write_text(json.dumps(log_data, indent=2))

        logger.error(f"Error processing response: {e}. Log: {log_file}")
        raise
