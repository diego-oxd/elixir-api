import json

from fastapi import APIRouter, HTTPException
from pydantic import ValidationError

from app.models.schemas import (
    CodeQueryRequest,
    CodeQueryResponse,
    SimpleCodebaseSummary,
)
from app.services.agent import query_codebase, query_codebase_json
from app.services.prompts import prompts

router = APIRouter(prefix="/code-query", tags=["code-query"])


@router.post("", response_model=CodeQueryResponse)
async def query_code(request: CodeQueryRequest):
    """
    Query a codebase using Claude Agent SDK.

    This endpoint is async and may take 15-45 seconds depending on the query complexity.
    """
    try:
        answer = await query_codebase(
            user_query=request.query,
            repo_path=request.repo_path,
        )
        return CodeQueryResponse(answer=answer)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))



@router.post("/test-structured-output", response_model=SimpleCodebaseSummary)
async def test_structured_output(repo_path: str):
    """
    Simple test endpoint to verify structured outputs work.

    This uses a minimal schema with just 5 fields to test the
    output_format feature before trying more complex schemas.

    Args:
        repo_path: Absolute path to the repository to analyze

    Returns:
        SimpleCodebaseSummary: Basic info about the codebase
    """
    prompt = """
    Analyze this codebase and return a JSON object with these fields:

    - primary_language: The main programming language (e.g., "Python", "JavaScript")
    - framework: The main framework used (e.g., "FastAPI", "React", "None")
    - total_files: Approximate count of source code files (integer)
    - has_tests: Whether the project has a test directory (boolean)
    - summary: One sentence describing what this project does

    Return ONLY valid JSON matching this structure.
    """

    try:
        result = await query_codebase_json(
            user_query=prompt,
            repo_path=repo_path,
            response_model=SimpleCodebaseSummary,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except ValidationError as e:
        raise HTTPException(
            status_code=502,
            detail=f"Schema validation error: {e.errors()}",
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/generate-docs")
async def generate_documentation(repo_path: str, prompt_name: str):
    """
    Generate documentation for a codebase using a specified prompt.

    Uses Claude's structured outputs feature to guarantee the response
    matches the prompt's schema. This may take 30-90 seconds for large codebases.

    All responses (success and failure) are logged to logs/agent_responses/
    for debugging and auditing.

    Args:
        repo_path: Absolute path to the repository to analyze
        prompt_name: Name of the prompt to use. Available options:
            - "api": API endpoints documentation
            - "data_model": Data model structure documentation
            - "project_overview": High-level project overview
            - "frontend": Frontend components and structure

    Returns:
        Structured documentation matching the prompt's schema.

    Raises:
        400: If the prompt_name is not recognized
        502: If the agent response is invalid (with log file path for debugging)
        500: Other unexpected errors
    """
    # Validate prompt name
    if prompt_name not in prompts:
        available_prompts = ", ".join(prompts.keys())
        raise HTTPException(
            status_code=400,
            detail=f"Unknown prompt name '{prompt_name}'. Available prompts: {available_prompts}",
        )

    prompt_config = prompts[prompt_name]

    try:
        result = await query_codebase_json(
            user_query=prompt_config["prompt_template"],
            repo_path=repo_path,
            response_model=prompt_config["schema"],
        )
        return result
    except ValueError as e:
        # These errors include the log file path
        raise HTTPException(
            status_code=502,
            detail=str(e),
        )
    except ValidationError as e:
        raise HTTPException(
            status_code=502,
            detail=f"Agent response doesn't match schema: {e.errors()}",
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
