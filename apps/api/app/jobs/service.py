from __future__ import annotations

from pathlib import Path

from app.jobs.models import JobLog, JobRecord, JobState
from app.projects.models import utc_now_iso
from app.projects.service import read_project, save_project


def append_job(
    outputs_dir: Path,
    project_id: str,
    job_type: str,
    label: str,
    input_paths: list[str] | None = None,
    provider: str | None = None,
    command: str | None = None,
) -> JobRecord:
    project = read_project(outputs_dir, project_id)
    job = JobRecord(
        job_type=job_type,
        label=label,
        input_paths=input_paths or [],
        provider=provider,
        command=command,
    )
    project.job_history.append(job.model_dump())
    project.updated_at = utc_now_iso()
    save_project(outputs_dir, project)
    return job


def update_job_state(
    outputs_dir: Path,
    project_id: str,
    job_id: str,
    state: JobState,
    message: str,
    output_paths: list[str] | None = None,
    error_message: str | None = None,
) -> JobRecord:
    project = read_project(outputs_dir, project_id)
    matches: list[tuple[int, JobRecord]] = []
    for index, raw_job in enumerate(project.job_history):
        job = JobRecord.model_validate(raw_job)
        if job.job_id == job_id:
            matches.append((index, job))
    if not matches:
        raise KeyError(f"Job not found: {job_id}")
    if len(matches) > 1:
        raise ValueError(f"Duplicate job_id found: {job_id}")

    index, job = matches[0]
    timestamp = utc_now_iso()
    job.state = state
    job.updated_at = timestamp
    if state == "running" and job.started_at is None:
        job.started_at = timestamp
    if state in ("succeeded", "failed"):
        job.ended_at = timestamp
    if state == "failed":
        job.error_message = error_message or message
    elif error_message is not None:
        job.error_message = error_message
    job.logs.append(JobLog(message=message))
    if output_paths:
        job.output_paths.extend(output_paths)
    job = JobRecord.model_validate(job.model_dump())
    project.job_history[index] = job.model_dump()
    project.updated_at = utc_now_iso()
    save_project(outputs_dir, project)
    return job
