from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from typing import Callable

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.projects.service import create_project, list_projects, read_project, update_project_title


MAX_PROJECT_ID_ATTEMPTS = 1440


class CreateProjectRequest(BaseModel):
    project_title: str = "untitled"


class UpdateProjectRequest(BaseModel):
    project_title: str


def timestamp_id(offset_minutes: int = 0) -> str:
    return (datetime.now() + timedelta(minutes=offset_minutes)).strftime("%y%m%d_%H%M")


def _project_response(project):
    return {"project": project.model_dump()}


def _raise_project_error(exc: Exception) -> None:
    if isinstance(exc, FileNotFoundError):
        raise HTTPException(status_code=404, detail="Project not found") from exc
    if isinstance(exc, ValueError):
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    raise exc


def create_projects_router(outputs_dir_provider: Callable[[], Path]) -> APIRouter:
    router = APIRouter(prefix="/api/projects", tags=["projects"])

    def outputs_dir() -> Path:
        return outputs_dir_provider()

    @router.get("")
    def get_projects(outputs: Path = Depends(outputs_dir)):
        return {"projects": [project.model_dump() for project in list_projects(outputs)]}

    @router.post("")
    def post_project(payload: CreateProjectRequest, outputs: Path = Depends(outputs_dir)):
        for offset in range(MAX_PROJECT_ID_ATTEMPTS):
            try:
                project = create_project(outputs, payload.project_title, timestamp_id(offset))
                return _project_response(project)
            except FileExistsError:
                continue
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc
        raise HTTPException(status_code=409, detail="Could not allocate a unique project_id")

    @router.get("/{project_id}")
    def get_project(project_id: str, outputs: Path = Depends(outputs_dir)):
        try:
            project = read_project(outputs, project_id)
        except (FileNotFoundError, ValueError) as exc:
            _raise_project_error(exc)
        return _project_response(project)

    @router.patch("/{project_id}")
    def patch_project(
        project_id: str,
        payload: UpdateProjectRequest,
        outputs: Path = Depends(outputs_dir),
    ):
        try:
            project = update_project_title(outputs, project_id, payload.project_title)
        except (FileNotFoundError, ValueError) as exc:
            _raise_project_error(exc)
        return _project_response(project)

    return router
