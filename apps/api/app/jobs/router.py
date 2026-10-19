from __future__ import annotations

from pathlib import Path
from typing import Callable, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator

from app.jobs.models import JobState
from app.jobs.service import append_job, update_job_state
from app.projects.service import read_project


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


def _bounded_optional(value: Optional[str], field_name: str, max_length: int) -> Optional[str]:
    if value is None:
        return None
    return _bounded_non_empty(value, field_name, max_length)


class CreateJobRequest(BaseModel):
    job_type: str
    label: str
    provider: Optional[str] = None
    command: Optional[str] = None
    input_paths: list[str] = Field(default_factory=list)

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
    def validate_provider(cls, value: Optional[str]) -> Optional[str]:
        return _bounded_optional(value, "provider", 120)

    @field_validator("command")
    @classmethod
    def validate_command(cls, value: Optional[str]) -> Optional[str]:
        return _bounded_optional(value, "command", 500)

    @field_validator("input_paths")
    @classmethod
    def validate_input_paths(cls, value: list[str]) -> list[str]:
        return _bounded_path_entries(value, "input_paths")


class UpdateJobRequest(BaseModel):
    state: JobState
    message: str
    error_message: Optional[str] = None
    output_paths: list[str] = Field(default_factory=list)

    @field_validator("message")
    @classmethod
    def validate_message(cls, value: str) -> str:
        return _bounded_non_empty(value, "message", 2000)

    @field_validator("error_message")
    @classmethod
    def validate_error_message(cls, value: Optional[str]) -> Optional[str]:
        return _bounded_optional(value, "error_message", 2000)

    @field_validator("output_paths")
    @classmethod
    def validate_output_paths(cls, value: list[str]) -> list[str]:
        return _bounded_path_entries(value, "output_paths")


def _raise_job_error(exc: Exception) -> None:
    if isinstance(exc, FileNotFoundError):
        raise HTTPException(status_code=404, detail="Project not found") from exc
    if isinstance(exc, KeyError):
        raise HTTPException(status_code=404, detail="Job not found") from exc
    if isinstance(exc, ValueError):
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    raise exc


def create_jobs_router(outputs_dir_provider: Callable[[], Path]) -> APIRouter:
    router = APIRouter(prefix="/api/projects/{project_id}/jobs", tags=["jobs"])

    def outputs_dir() -> Path:
        return outputs_dir_provider()

    @router.get("")
    def get_jobs(project_id: str, outputs: Path = Depends(outputs_dir)):
        try:
            project = read_project(outputs, project_id)
        except (FileNotFoundError, ValueError) as exc:
            _raise_job_error(exc)
        return {"jobs": project.job_history}

    @router.post("")
    def post_job(project_id: str, payload: CreateJobRequest, outputs: Path = Depends(outputs_dir)):
        try:
            job = append_job(
                outputs,
                project_id,
                payload.job_type,
                payload.label,
                payload.input_paths,
                provider=payload.provider,
                command=payload.command,
            )
        except (FileNotFoundError, ValueError) as exc:
            _raise_job_error(exc)
        return {"job": job.model_dump()}

    @router.patch("/{job_id}")
    def patch_job(
        project_id: str,
        job_id: str,
        payload: UpdateJobRequest,
        outputs: Path = Depends(outputs_dir),
    ):
        try:
            job = update_job_state(
                outputs,
                project_id,
                job_id,
                payload.state,
                payload.message,
                payload.output_paths,
                error_message=payload.error_message,
            )
        except (FileNotFoundError, KeyError, ValueError) as exc:
            _raise_job_error(exc)
        return {"job": job.model_dump()}

    return router
