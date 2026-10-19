from pathlib import Path

import pytest
from pydantic import ValidationError

from app.jobs.models import JobLog, JobRecord
from app.jobs.service import append_job, update_job_state
from app.projects.models import Project
from app.projects.service import create_project, read_project, save_project


def test_append_job_records_pending_job(tmp_path: Path):
    create_project(tmp_path, project_title="작업", now="261011_2130")

    job = append_job(
        tmp_path,
        "261011_2130",
        job_type="reference_search",
        label="Reference search",
        provider="youtube",
        command="search references",
    )

    project = read_project(tmp_path, "261011_2130")
    assert job.job_id
    assert job.state == "pending"
    assert job.provider == "youtube"
    assert job.command == "search references"
    assert job.started_at is None
    assert job.ended_at is None
    assert job.error_message is None
    assert project.job_history[0]["job_type"] == "reference_search"


def test_update_job_state_adds_log_line(tmp_path: Path):
    create_project(tmp_path, project_title="작업", now="261011_2130")
    job = append_job(tmp_path, "261011_2130", job_type="reference_search", label="Reference search")

    updated = update_job_state(
        tmp_path,
        "261011_2130",
        job.job_id,
        state="failed",
        message="YouTube key missing",
    )

    assert updated.state == "failed"
    assert updated.logs[-1].message == "YouTube key missing"


def test_update_job_state_persists_state_log_and_output_paths(tmp_path: Path):
    create_project(tmp_path, project_title="작업", now="261011_2130")
    job = append_job(tmp_path, "261011_2130", job_type="reference_search", label="Reference search")

    update_job_state(
        tmp_path,
        "261011_2130",
        job.job_id,
        state="succeeded",
        message="References saved",
        output_paths=["references/items.json"],
    )

    project = read_project(tmp_path, "261011_2130")
    persisted = JobRecord.model_validate(project.job_history[0])
    assert persisted.state == "succeeded"
    assert persisted.ended_at is not None
    assert persisted.logs[-1].message == "References saved"
    assert persisted.output_paths == ["references/items.json"]


def test_update_job_state_tracks_running_start_and_failure_error(tmp_path: Path):
    create_project(tmp_path, project_title="작업", now="261011_2130")
    job = append_job(tmp_path, "261011_2130", job_type="reference_search", label="Reference search")

    running = update_job_state(
        tmp_path,
        "261011_2130",
        job.job_id,
        state="running",
        message="Started",
    )
    failed = update_job_state(
        tmp_path,
        "261011_2130",
        job.job_id,
        state="failed",
        message="Missing key",
        error_message="YouTube API key missing",
    )

    assert running.started_at is not None
    assert running.ended_at is None
    assert failed.started_at == running.started_at
    assert failed.ended_at is not None
    assert failed.error_message == "YouTube API key missing"


def test_update_job_state_missing_job_raises_key_error(tmp_path: Path):
    create_project(tmp_path, project_title="작업", now="261011_2130")

    with pytest.raises(KeyError):
        update_job_state(
            tmp_path,
            "261011_2130",
            "missing-job",
            state="failed",
            message="No matching job",
        )


def test_update_job_state_duplicate_job_ids_raise_value_error(tmp_path: Path):
    create_project(tmp_path, project_title="작업", now="261011_2130")
    job = append_job(tmp_path, "261011_2130", job_type="reference_search", label="Reference search")
    project = read_project(tmp_path, "261011_2130")
    project.job_history.append(dict(project.job_history[0]))
    save_project(tmp_path, project)

    with pytest.raises(ValueError):
        update_job_state(
            tmp_path,
            "261011_2130",
            job.job_id,
            state="failed",
            message="Duplicate job",
        )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("job_type", "   "),
        ("label", "   "),
    ],
)
def test_job_record_rejects_empty_required_text(field: str, value: str):
    payload = {"job_type": "reference_search", "label": "Reference search", field: value}

    with pytest.raises(ValidationError):
        JobRecord(**payload)


@pytest.mark.parametrize("path", ["/tmp/out.mp4", "../secret.txt", "outputs/../secret.txt"])
def test_job_record_rejects_unsafe_paths(path: str):
    with pytest.raises(ValidationError):
        JobRecord(job_type="script", label="Script", input_paths=[path])


def test_job_log_rejects_empty_message():
    with pytest.raises(ValidationError):
        JobLog(message="   ")


def test_save_project_refuses_missing_project_folder(tmp_path: Path):
    project = Project(
        project_id="261011_2130",
        project_title="작업",
        display_name="261011_작업",
        created_at="2026-10-11T21:30:00+00:00",
        updated_at="2026-10-11T21:30:00+00:00",
    )

    with pytest.raises(FileNotFoundError):
        save_project(tmp_path, project)


def test_save_project_refuses_missing_project_json(tmp_path: Path):
    project = Project(
        project_id="261011_2130",
        project_title="작업",
        display_name="261011_작업",
        created_at="2026-10-11T21:30:00+00:00",
        updated_at="2026-10-11T21:30:00+00:00",
    )
    (tmp_path / "261011_2130").mkdir()

    with pytest.raises(FileNotFoundError):
        save_project(tmp_path, project)
