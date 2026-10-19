import json
import os
import re
import tempfile
from datetime import datetime
from pathlib import Path

from pydantic import ValidationError

from app.projects.models import Project, StepName, StepState, default_step_statuses, utc_now_iso


PROJECT_ID_RE = re.compile(r"^\d{6}_\d{4}$")


def _validate_project_id(project_id: str) -> str:
    if not PROJECT_ID_RE.fullmatch(project_id):
        raise ValueError("project_id must match YYMMDD_HHMM")
    try:
        datetime.strptime(project_id, "%y%m%d_%H%M")
    except ValueError as exc:
        raise ValueError("project_id must be a valid YYMMDD_HHMM timestamp") from exc
    return project_id


def _ensure_contained(base_dir: Path, path: Path) -> Path:
    resolved_base = base_dir.resolve()
    resolved_path = path.resolve()
    try:
        resolved_path.relative_to(resolved_base)
    except ValueError as exc:
        raise ValueError("project path must stay under outputs_dir") from exc
    return resolved_path


def _project_path(outputs_dir: Path, project_id: str) -> Path:
    valid_project_id = _validate_project_id(project_id)
    return _ensure_contained(outputs_dir, outputs_dir / valid_project_id)


def _project_json_path(outputs_dir: Path, project_id: str) -> Path:
    return _project_path(outputs_dir, project_id) / "project.json"


def _display_name(project_id: str, project_title: str) -> str:
    yymmdd = project_id.split("_")[0]
    clean_title = project_title.strip() or "untitled"
    return f"{yymmdd}_{clean_title}"


def _write_project(outputs_dir: Path, project: Project, create_missing: bool) -> None:
    folder = _project_path(outputs_dir, project.project_id)
    path = folder / "project.json"
    if create_missing:
        folder.mkdir(parents=True, exist_ok=False)
    elif not folder.is_dir() or not path.is_file():
        raise FileNotFoundError(f"Project does not exist: {project.project_id}")
    payload = json.dumps(project.model_dump(), ensure_ascii=False, indent=2)
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=folder,
            prefix=".project.",
            suffix=".tmp",
            delete=False,
        ) as temp_file:
            temp_path = Path(temp_file.name)
            temp_file.write(payload)
            temp_file.flush()
            os.fsync(temp_file.fileno())
        os.replace(temp_path, path)
    finally:
        if temp_path is not None and temp_path.exists():
            temp_path.unlink()


def save_project(outputs_dir: Path, project: Project) -> None:
    _write_project(outputs_dir, project, create_missing=False)


def create_project(outputs_dir: Path, project_title: str, now: str) -> Project:
    project_id = _validate_project_id(now)
    timestamp = utc_now_iso()
    project = Project(
        project_id=project_id,
        project_title=project_title.strip() or "untitled",
        display_name=_display_name(project_id, project_title),
        created_at=timestamp,
        updated_at=timestamp,
        step_statuses=default_step_statuses(),
    )
    _write_project(outputs_dir, project, create_missing=True)
    return project


def read_project(outputs_dir: Path, project_id: str) -> Project:
    path = _project_json_path(outputs_dir, project_id)
    data = json.loads(path.read_text(encoding="utf-8"))
    return Project.model_validate(data)


def list_projects(outputs_dir: Path) -> list[Project]:
    if not outputs_dir.exists():
        return []
    projects: list[Project] = []
    for child in outputs_dir.iterdir():
        project_json = child / "project.json"
        if child.is_dir() and project_json.exists():
            try:
                project = Project.model_validate_json(project_json.read_text(encoding="utf-8"))
                _validate_project_id(project.project_id)
                projects.append(project)
            except (ValidationError, ValueError):
                continue
    return sorted(projects, key=lambda project: project.project_id, reverse=True)


def update_project_title(outputs_dir: Path, project_id: str, project_title: str) -> Project:
    project = read_project(outputs_dir, project_id)
    project.project_title = project_title.strip() or "untitled"
    project.display_name = _display_name(project.project_id, project.project_title)
    project.updated_at = utc_now_iso()
    _write_project(outputs_dir, project, create_missing=False)
    return project


def update_project_step(
    outputs_dir: Path,
    project_id: str,
    step_name: StepName,
    state: StepState,
    message: str,
) -> Project:
    project = read_project(outputs_dir, project_id)
    matching_status = None
    for status in project.step_statuses:
        if status.name == step_name:
            matching_status = status
            break
    if matching_status is None:
        raise ValueError(f"Step status not found: {step_name}")
    project.current_step = step_name
    matching_status.state = state
    matching_status.message = message
    project.updated_at = utc_now_iso()
    save_project(outputs_dir, project)
    return project
