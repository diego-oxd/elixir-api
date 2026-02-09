from pydantic import BaseModel, Field
from typing import List, Optional, Literal

class AuthInfo(BaseModel):
    required: bool
    scheme: Optional[str] = Field(description="e.g., JWT, Session, API Key, or None")

class InputParameter(BaseModel):
    name: str
    data_type: str = Field(description="The primitive (string, int) or object type")
    location: Literal["path", "query", "body", "header"]
    required: bool
    description: Optional[str] = None

class OutputField(BaseModel):
    name: str
    data_type: str = Field(description="The primitive or object type returned")
    description: Optional[str] = None

class APIEndpoint(BaseModel):
    identifier: str = Field(description="The route path or method name")
    method: str = Field(description="GET, POST, RPC, WS, etc.")
    summary: str = Field(description="What this endpoint does for a newcomer")
    file_path: str = Field(description="Source file location")
    auth: AuthInfo
    inputs: List[InputParameter] = Field(description="All required and optional inputs")
    outputs: List[OutputField] = Field(description="Fields included in a successful response")

class APIDocumentation(BaseModel):
    framework: str
    base_url: Optional[str] = None
    endpoints: List[APIEndpoint]


prompt = """
# Task: API Surface Area Extraction

## Objective
Act as a technical architect to map the backend API surface area. Your goal is to provide a clean, type-safe reference for developers onboarding to this codebase. You must identify every client-accessible entry point and document exactly what data it requires and returns.

## 1. Discovery Strategy (Pre-Analysis)
To ensure 100% coverage, your agentic search must:
1.  **Locate Route Registrations**: Search for router files, controller decorators (e.g., `@Get`, `@PostMapping`), or framework-specific method exports (e.g., `Meteor.methods`).
2.  **Identify Schemas**: Look for validation logic (Zod, Joi, Pydantic, DTO classes) to determine input/output shapes and data types.
3.  **Check Middleware**: Trace the route definitions to identify if authentication middleware is applied.

## 2. Extraction Scope
### Requirements:
- **Separation**: Keep `inputs` and `outputs` in separate lists for each endpoint.
- **Typing**: Every field must have a `data_type`. Use the specific class name (e.g., `UserUpdateDTO`) if it is a complex object.
- **Conciseness**: Descriptions should be one-sentence summaries of the field's purpose.

### Exclusions (Do Not Extract):
- Implementation logic or side effects (e.g., "Sends an email").
- Error scenarios (400, 401, 500 responses).
- Cache-control or Rate-limiting details.
- Hyperlinks to other endpoints.

## 3. Mandatory Reasoning Checklist
*Before outputting JSON, perform this internal verification:*

- [ ] **Discovery**: Have I scanned the entire directory for all possible routes?
- [ ] **Inputs**: Are all path, query, and body parameters listed in the `inputs` array?
- [ ] **Outputs**: Are the keys of the successful response object listed in the `outputs` array?
- [ ] **Type Check**: Does every single input and output have an explicit `data_type`?
- [ ] **Auth Check**: Did I correctly identify if the route is public or protected?
- [ ] **Formatting**: Is the JSON structure flat (APIDocumentation -> Endpoint -> Input/Output)?

## 4. Final Output
Return a structured JSON object according to the `APIDocumentation` schema. Ensure the documentation is "Developer-Ready"—meaning a developer could write a client-side fetch request solely based on your output.
"""


api_prompt = {
    "name": "api_endpoint_analyzer",
    "description": "Analyzes API endpoints and provides detailed information about their structure and functionality.",
    "prompt_template": prompt,
    "schema": APIDocumentation,
}