from pathlib import Path

from fastapi.testclient import TestClient

from app.main import create_app
from app.projects import router as projects_router


def test_health_endpoint(tmp_path: Path):
    client = TestClient(create_app(repo_root=tmp_path))

    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json()["ok"] is True


def test_create_and_list_projects(tmp_path: Path):
    client = TestClient(create_app(repo_root=tmp_path))

    created = client.post("/api/projects", json={"project_title": "첫 프로젝트"})
    listed = client.get("/api/projects")

    assert created.status_code == 200
    assert listed.status_code == 200
    assert listed.json()["projects"][0]["project_title"] == "첫 프로젝트"


def test_update_project_title(tmp_path: Path):
    client = TestClient(create_app(repo_root=tmp_path))
    project_id = client.post("/api/projects", json={"project_title": "초기"}).json()["project"][
        "project_id"
    ]

    response = client.patch(f"/api/projects/{project_id}", json={"project_title": "변경"})

    assert response.status_code == 200
    assert response.json()["project"]["project_title"] == "변경"


def test_create_multiple_projects_avoids_timestamp_collision(tmp_path: Path):
    client = TestClient(create_app(repo_root=tmp_path))

    first = client.post("/api/projects", json={"project_title": "첫 프로젝트"})
    second = client.post("/api/projects", json={"project_title": "두번째 프로젝트"})

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["project"]["project_id"] != second.json()["project"]["project_id"]


def test_forced_project_timestamp_collision_retries_next_id(tmp_path: Path, monkeypatch):
    ids = {0: "260101_0000", 1: "260101_0001"}
    attempted_offsets: list[int] = []

    def fixed_timestamp_id(offset_minutes: int = 0) -> str:
        attempted_offsets.append(offset_minutes)
        return ids[offset_minutes]

    monkeypatch.setattr(projects_router, "timestamp_id", fixed_timestamp_id)
    client = TestClient(create_app(repo_root=tmp_path))

    first = client.post("/api/projects", json={"project_title": "첫 프로젝트"})
    second = client.post("/api/projects", json={"project_title": "두번째 프로젝트"})

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["project"]["project_id"] == "260101_0000"
    assert second.json()["project"]["project_id"] == "260101_0001"
    assert attempted_offsets == [0, 0, 1]


def test_job_get_post_patch_happy_path(tmp_path: Path):
    client = TestClient(create_app(repo_root=tmp_path))
    project_id = client.post("/api/projects", json={"project_title": "작업 프로젝트"}).json()[
        "project"
    ]["project_id"]

    initial_jobs = client.get(f"/api/projects/{project_id}/jobs")
    created = client.post(
        f"/api/projects/{project_id}/jobs",
        json={
            "job_type": "script",
            "label": "대본 생성",
            "provider": "openai",
            "command": "generate script",
            "input_paths": ["inputs/topic.txt"],
        },
    )
    job_id = created.json()["job"]["job_id"]
    updated = client.patch(
        f"/api/projects/{project_id}/jobs/{job_id}",
        json={
            "state": "succeeded",
            "message": "완료",
            "output_paths": ["outputs/script.md"],
        },
    )
    listed = client.get(f"/api/projects/{project_id}/jobs")

    assert initial_jobs.status_code == 200
    assert initial_jobs.json()["jobs"] == []
    assert created.status_code == 200
    assert created.json()["job"]["job_type"] == "script"
    assert created.json()["job"]["provider"] == "openai"
    assert created.json()["job"]["command"] == "generate script"
    assert created.json()["job"]["started_at"] is None
    assert created.json()["job"]["ended_at"] is None
    assert updated.status_code == 200
    assert updated.json()["job"]["state"] == "succeeded"
    assert updated.json()["job"]["ended_at"] is not None
    assert updated.json()["job"]["logs"][0]["message"] == "완료"
    assert listed.status_code == 200
    assert listed.json()["jobs"][0]["job_id"] == job_id


def test_missing_project_errors_are_sanitized(tmp_path: Path):
    client = TestClient(create_app(repo_root=tmp_path))

    project_response = client.get("/api/projects/991231_2359")
    job_response = client.get("/api/projects/991231_2359/jobs")

    assert project_response.status_code == 404
    assert project_response.json()["detail"] == "Project not found"
    assert str(tmp_path) not in project_response.text
    assert job_response.status_code == 404
    assert job_response.json()["detail"] == "Project not found"
    assert str(tmp_path) not in job_response.text


def test_missing_job_error_is_sanitized(tmp_path: Path):
    client = TestClient(create_app(repo_root=tmp_path))
    project_id = client.post("/api/projects", json={"project_title": "작업 프로젝트"}).json()[
        "project"
    ]["project_id"]

    response = client.patch(
        f"/api/projects/{project_id}/jobs/missing-job",
        json={"state": "failed", "message": "실패"},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Job not found"
    assert str(tmp_path) not in response.text


def test_invalid_job_payload_returns_422_for_blank_fields(tmp_path: Path):
    client = TestClient(create_app(repo_root=tmp_path))
    project_id = client.post("/api/projects", json={"project_title": "작업 프로젝트"}).json()[
        "project"
    ]["project_id"]

    create_response = client.post(
        f"/api/projects/{project_id}/jobs",
        json={"job_type": " ", "label": "", "input_paths": ["inputs/topic.txt", " "]},
    )
    patch_response = client.patch(
        f"/api/projects/{project_id}/jobs/anything",
        json={"state": "succeeded", "message": " ", "output_paths": [" "]},
    )

    assert create_response.status_code == 422
    assert patch_response.status_code == 422


def test_invalid_job_payload_returns_422_for_unsafe_paths(tmp_path: Path):
    client = TestClient(create_app(repo_root=tmp_path))
    project_id = client.post("/api/projects", json={"project_title": "작업 프로젝트"}).json()[
        "project"
    ]["project_id"]

    create_response = client.post(
        f"/api/projects/{project_id}/jobs",
        json={"job_type": "script", "label": "대본 생성", "input_paths": ["../secret.txt"]},
    )
    patch_response = client.patch(
        f"/api/projects/{project_id}/jobs/anything",
        json={"state": "succeeded", "message": "완료", "output_paths": ["/tmp/out.mp4"]},
    )

    assert create_response.status_code == 422
    assert patch_response.status_code == 422


def test_settings_status_exposes_key_presence_not_secret_values(tmp_path: Path):
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "local.settings.json").write_text(
        '{"openai_api_key":"openai-secret","youtube_api_key":"youtube-secret",'
        '"higgsfield_api_key":"higgs-secret","reference_voice_text":"secret reference text"}',
        encoding="utf-8",
    )
    client = TestClient(create_app(repo_root=tmp_path))

    response = client.get("/api/settings/status")

    assert response.status_code == 200
    assert response.json()["openai_api_key"] is True
    assert response.json()["youtube_api_key"] is True
    assert response.json()["higgsfield_api_key"] is True
    assert response.json()["reference_voice_text"] is True
    assert "secret" not in response.text
