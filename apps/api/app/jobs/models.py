from __future__ import annotations

from pathlib import Path
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator

from app.projects.models import utc_now_iso


JobState = Literal["pending", "running", "succeeded", "failed"]


def _bounded_non_empty(value: str, field_name: str, max_length: int) -> str:
    stripped = value.strip()
    if not stripped:
        raise ValueError(f"{field_name} must not be empty")
    if len(stripped) > max_length:
        raise ValueError(f"{field_name} must be at most {max_length} characters")
    return stripped


def _bounded_path_entries(values: list[str], field_name: str) -> list[str]:
    safe_paths: list[str] = []
    for value in values:
        path_value = _bounded_non_empty(value, field_name, 1024)
        path = Path(path_value)
        if path.is_absolute() or ".." in path.parts:
            raise ValueError(f"{field_name} entries must be relative paths without traversal")
        safe_paths.append(path_value)
    return safe_paths


def _bounded_optional(value: str | None, field_name: str, max_length: int) -> str | None:
    if value is None:
        return None
    return _bounded_non_empty(value, field_name, max_length)


class JobLog(BaseModel):
    timestamp: str = Field(default_factory=utc_now_iso)
    message: str

    @field_validator("message")
    @classmethod
    def validate_message(cls, value: str) -> str:
        return _bounded_non_empty(value, "message", 2000)


class JobRecord(BaseModel):
    job_id: str = Field(default_factory=lambda: uuid4().hex)
    job_type: str
    label: str
    provider: str | None = None
    command: str | None = None
    state: JobState = "pending"
    created_at: str = Field(default_factory=utc_now_iso)
    updated_at: str = Field(default_factory=utc_now_iso)
    started_at: str | None = None
    ended_at: str | None = None
    error_message: str | None = None
    input_paths: list[str] = Field(default_factory=list)
    output_paths: list[str] = Field(default_factory=list)
    logs: list[JobLog] = Field(default_factory=list)

    @field_validator("job_type")
    @classmethod
    def validate_job_type(cls, value: str) -> str:
        return _bounded_non_empty(value, "job_type", 120)

    @field_validator("label")
    @classmethod
    def validate_label(cls, value: str) -> str:
        return _bounded_non_empty(value, "label", 200)

    @field_validator("provider")
    @classmethod
    def validate_provider(cls, value: str | None) -> str | None:
        return _bounded_optional(value, "provider", 120)

    @field_validator("command")
    @classmethod
    def validate_command(cls, value: str | None) -> str | None:
        return _bounded_optional(value, "command", 500)

    @field_validator("error_message")
    @classmethod
    def validate_error_message(cls, value: str | None) -> str | None:
        return _bounded_optional(value, "error_message", 2000)

    @field_validator("input_paths", "output_paths")
    @classmethod
    def validate_paths(cls, value: list[str], info) -> list[str]:
        return _bounded_path_entries(value, info.field_name)
