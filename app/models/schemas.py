from typing import Any

from pydantic import BaseModel, ConfigDict, field_validator


class UpdateModel(BaseModel):
    """Base model for update operations that validates no MongoDB operators."""

    model_config = ConfigDict(extra="allow")

    @field_validator("*", mode="before")
    @classmethod
    def validate_no_dollar_keys(cls, v: Any, info) -> Any:
        """Prevent MongoDB operator injection in field names."""
        if info.field_name and info.field_name.startswith("$"):
            raise ValueError("Field names cannot start with '$'")
        return v

    def model_post_init(self, __context: Any) -> None:
        """Validate that no extra fields start with $."""
        for key in self.model_extra or {}:
            if key.startswith("$"):
                raise ValueError("Field names cannot start with '$'")


# Project models
class ProjectCreate(BaseModel):
    model_config = ConfigDict(extra="allow")

    name: str
    description: str | None = None
    repo_path: str | None = None


class ProjectResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str
    name: str
    description: str | None = None
    repo_path: str | None = None


class ProjectUpdate(UpdateModel):
    model_config = ConfigDict(extra="forbid")

    description: str | None = None
    repo_path: str | None = None


class ProjectListItem(BaseModel):
    id: str
    name: str
    description: str | None = None
    repo_path: str | None = None


class AddCodebaseRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    repo_path: str


# Page models
class PageCreate(BaseModel):
    model_config = ConfigDict(extra="allow")

    name: str
    title: str
    content: str
    project_id: str


class PageResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str
    name: str
    title: str
    content: str
    project_id: str


class PageUpdate(UpdateModel):
    model_config = ConfigDict(extra="forbid")

    content: str | None = None


# CodeSample models
class CodeSampleCreate(BaseModel):
    model_config = ConfigDict(extra="allow")

    title: str
    language: str
    description: str
    code_string: str
    project_id: str


class CodeSampleResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str
    title: str
    language: str
    description: str
    code_string: str
    project_id: str


class CodeSampleListItem(BaseModel):
    id: str
    title: str


class CodeSampleUpdate(UpdateModel):
    model_config = ConfigDict(extra="forbid")

    title: str | None = None
    language: str | None = None
    description: str | None = None
    code_string: str | None = None


# DocPage models
class DocPageCreate(BaseModel):
    model_config = ConfigDict(extra="allow")

    title: str
    content: str
    project_id: str


class DocPageResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str
    title: str
    content: str
    project_id: str


class DocPageListItem(BaseModel):
    id: str
    title: str


class DocPageUpdate(UpdateModel):
    model_config = ConfigDict(extra="forbid")

    title: str | None = None
    content: str | None = None


# Code Query models (Claude Agent SDK)
class CodeQueryRequest(BaseModel):
    query: str
    repo_path: str


class CodeQueryResponse(BaseModel):
    answer: str


# Simple test model for structured outputs
class SimpleCodebaseSummary(BaseModel):
    """Simple schema to test structured outputs."""

    primary_language: str
    framework: str
    total_files: int
    has_tests: bool
    summary: str

