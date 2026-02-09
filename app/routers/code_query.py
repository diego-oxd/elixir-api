import json

from fastapi import APIRouter, HTTPException
from pydantic import ValidationError

from app.models.schemas import (
    CodeQueryRequest,
    CodeQueryResponse,
    SimpleCodebaseSummary,
)
from app.services.agent import query_codebase, query_codebase_json
from app.services.api_prompt import APIDocumentation, api_prompt

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


@router.post("/analyze-api", response_model=APIDocumentation)
async def analyze_api_endpoints(repo_path: str):
    """
    Analyze a codebase and extract all API endpoints with their schemas.

    Uses Claude's structured outputs feature to guarantee the response
    matches the APIDocumentation schema. This may take 30-90 seconds
    for large codebases.

    All responses (success and failure) are logged to logs/agent_responses/
    for debugging and auditing.

    Args:
        repo_path: Absolute path to the repository to analyze

    Returns:
        APIDocumentation: Structured documentation of all API endpoints including
        inputs, outputs, authentication, and file locations.

    Raises:
        502: If the agent response is invalid (with log file path for debugging)
        500: Other unexpected errors
    """
    try:
        result = await query_codebase_json(
            user_query=api_prompt["prompt_template"],
            repo_path=repo_path,
            response_model=api_prompt["schema"],
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
