from pathlib import Path

import httpx
from fastapi.testclient import TestClient

from app.main import create_app
from app.references.models import ReferenceCandidate


class FakeYouTubeClient:
    def __init__(self, api_key: str):
        self.api_key = api_key

    def search(self, request):
        return [
            ReferenceCandidate(
                video_id="highratio1",
                url="https://www.youtube.com/watch?v=highratio1",
                title="High Ratio",
                channel_id="channel-1",
                channel_name="채널",
                thumbnail_url="https://example.com/high.jpg",
                upload_date="2026-10-01T00:00:00Z",
                duration_seconds=44,
                view_count=100000,
                subscriber_count=1000,
                source_type="search",
            ),
            ReferenceCandidate(
                video_id="lowratio1",
                url="https://www.youtube.com/watch?v=lowratio1",
                title="Low Ratio",
                channel_id="channel-2",
                channel_name="채널",
                thumbnail_url="https://example.com/low.jpg",
                upload_date="2026-10-01T00:00:00Z",
                duration_seconds=44,
                view_count=100000,
                subscriber_count=10000,
                source_type="search",
            ),
        ]

    def get_direct(self, url: str):
        return ReferenceCandidate(
            video_id="direct1",
            url=url,
            title="Direct",
            channel_id="channel-3",
            channel_name="직접 채널",
            thumbnail_url="https://example.com/direct.jpg",
            upload_date="2026-10-01T00:00:00Z",
            duration_seconds=42,
            view_count=200000,
            subscriber_count=5000,
            source_type="direct",
        )


class FailingYouTubeClient:
    def __init__(self, api_key: str):
        self.api_key = api_key

    def search(self, request):
        raise httpx.ConnectError("network down")

    def get_direct(self, url: str):
        raise httpx.ConnectError("network down")


class FakeTranscriptionClient:
    def __init__(self, api_key: str, model: str):
        self.api_key = api_key
        self.model = model

    def transcribe(self, audio_path: Path):
        return {
            "text": "첫 문장입니다.",
            "segments": [{"start": 0, "end": 1, "text": "첫 문장입니다."}],
        }


class FailingTranscriptionClient:
    def __init__(self, api_key: str, model: str):
        self.api_key = api_key
        self.model = model

    def transcribe(self, audio_path: Path):
        raise RuntimeError("openai unavailable")


class FakeAnalysisClient:
    def __init__(self, api_key: str, model: str):
        self.api_key = api_key
        self.model = model

    def analyze(self, prompt: str):
        return {
            "primary_structure": "common-sense conflict",
            "supporting_structures": ["question"],
            "hook_analysis": "첫 문장이 상식을 흔듭니다.",
            "curiosity_gap": "왜 그런지 궁금하게 만듭니다.",
            "retention_analysis": "중간에 반전을 넣습니다.",
            "payoff_analysis": "끝에서 답을 줍니다.",
            "risk_notes": ["근거가 약하면 과장처럼 보입니다."],
            "reusable_structure_notes": "상식 제시, 의문, 반전, 결론 순서.",
            "section_breakdown": [
                {
                    "section": "Hook",
                    "script_excerpt": "이걸 모르면 손해입니다.",
                    "viewer_reaction": "멈춥니다.",
                    "purpose": "궁금증",
                }
            ],
        }


class FailingAnalysisClient:
    def __init__(self, api_key: str, model: str):
        self.api_key = api_key
        self.model = model

    def analyze(self, prompt: str):
        raise RuntimeError("analysis unavailable")


class InvalidAnalysisClient:
    def __init__(self, api_key: str, model: str):
        self.api_key = api_key
        self.model = model

    def analyze(self, prompt: str):
        return {"primary_structure": "missing fields"}


def fake_audio_extractor(project_dir: Path, url: str, yt_dlp_binary: str) -> Path:
    output = project_dir / "reference_audio.wav"
    output.write_bytes(b"extracted audio")
    return output


def create_project(client: TestClient) -> str:
    return client.post("/api/projects", json={"project_title": "레퍼런스"}).json()["project"][
        "project_id"
    ]


def step_state(project: dict, step_name: str) -> str:
    return next(step["state"] for step in project["step_statuses"] if step["name"] == step_name)


def step_message(project: dict, step_name: str) -> str:
    return next(step["message"] for step in project["step_statuses"] if step["name"] == step_name)


def test_search_direct_select_and_restore_reference_state(tmp_path: Path):
    client = TestClient(create_app(repo_root=tmp_path, youtube_client_factory=FakeYouTubeClient))
    project_id = create_project(client)

    created_project = client.get(f"/api/projects/{project_id}").json()["project"]
    search = client.post(f"/api/projects/{project_id}/reference/search", json={"keyword": "돈"})
    after_search_project = client.get(f"/api/projects/{project_id}").json()["project"]
    direct = client.post(
        f"/api/projects/{project_id}/reference/direct",
        json={"url": "https://www.youtube.com/watch?v=direct1"},
    )
    selected = client.post(f"/api/projects/{project_id}/reference/select", json={"video_id": "direct1"})
    restored = client.get(f"/api/projects/{project_id}/reference")
    project = client.get(f"/api/projects/{project_id}").json()["project"]

    assert step_state(created_project, "Reference") != "succeeded"
    assert search.status_code == 200
    assert [item["video_id"] for item in search.json()["candidates"]] == [
        "highratio1",
        "lowratio1",
    ]
    assert step_state(after_search_project, "Reference") != "succeeded"
    assert direct.status_code == 200
    assert [item["video_id"] for item in direct.json()["candidates"]] == [
        "highratio1",
        "direct1",
        "lowratio1",
    ]
    assert selected.status_code == 200
    assert restored.status_code == 200
    assert restored.json()["selected_reference"]["video_id"] == "direct1"
    assert project["selected_reference_path"] == "selected_reference.json"
    assert project["generated_files"]["selected_reference"] == "selected_reference.json"
    assert project["current_step"] == "STT"
    assert step_state(project, "Reference") == "succeeded"
    assert step_state(project, "STT") == "waiting"
    assert step_message(project, "STT") == "Reference selected. Ready for audio and STT."


def test_reference_search_requires_youtube_key(tmp_path: Path):
    client = TestClient(create_app(repo_root=tmp_path))
    project_id = create_project(client)

    response = client.post(f"/api/projects/{project_id}/reference/search", json={"keyword": "돈"})
    project = client.get(f"/api/projects/{project_id}").json()["project"]

    assert response.status_code == 400
    assert response.json()["detail"] == "YouTube API key is missing"
    assert project["job_history"][-1]["state"] == "failed"
    assert project["job_history"][-1]["error_message"] == "YouTube API key is missing"


def test_reference_provider_failure_marks_job_failed(tmp_path: Path):
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "local.settings.json").write_text('{"youtube_api_key":"key"}', encoding="utf-8")
    client = TestClient(create_app(repo_root=tmp_path, youtube_client_factory=FailingYouTubeClient))
    project_id = create_project(client)

    response = client.post(f"/api/projects/{project_id}/reference/search", json={"keyword": "돈"})
    project = client.get(f"/api/projects/{project_id}").json()["project"]

    assert response.status_code == 400
    assert "network down" in response.json()["detail"]
    assert project["job_history"][-1]["state"] == "failed"
    assert "network down" in project["job_history"][-1]["error_message"]


def test_reselecting_reference_clears_downstream_outputs(tmp_path: Path):
    client = TestClient(create_app(repo_root=tmp_path, youtube_client_factory=FakeYouTubeClient))
    project_id = create_project(client)
    client.post(f"/api/projects/{project_id}/reference/search", json={"keyword": "돈"})
    client.post(
        f"/api/projects/{project_id}/reference/direct",
        json={"url": "https://www.youtube.com/watch?v=direct1"},
    )
    project_dir = tmp_path / "outputs" / project_id
    (project_dir / "reference_audio.mp3").write_bytes(b"old audio")
    (project_dir / "reference_script.md").write_text("old script", encoding="utf-8")
    (project_dir / "reference_analysis.json").write_text("{}", encoding="utf-8")
    (project_dir / "reference_analysis.md").write_text("old analysis", encoding="utf-8")

    response = client.post(f"/api/projects/{project_id}/reference/select", json={"video_id": "direct1"})
    restored = client.get(f"/api/projects/{project_id}/reference").json()
    project = client.get(f"/api/projects/{project_id}").json()["project"]

    assert response.status_code == 200
    assert not (project_dir / "reference_audio.mp3").exists()
    assert restored["reference_script"] is None
    assert restored["analysis"] is None
    assert restored["analysis_markdown"] is None
    assert "reference_script" not in project["generated_files"]
    assert step_state(project, "Analysis") == "waiting"


def test_reselecting_reference_clears_script_outputs(tmp_path: Path):
    client = TestClient(create_app(repo_root=tmp_path, youtube_client_factory=FakeYouTubeClient))
    project_id = create_project(client)
    client.post(f"/api/projects/{project_id}/reference/search", json={"keyword": "돈"})
    client.post(
        f"/api/projects/{project_id}/reference/direct",
        json={"url": "https://www.youtube.com/watch?v=direct1"},
    )
    project_dir = tmp_path / "outputs" / project_id
    (project_dir / "candidates.json").write_text("[]", encoding="utf-8")
    (project_dir / "selected_script_candidate.json").write_text("{}", encoding="utf-8")
    (project_dir / "final_script.md").write_text("old", encoding="utf-8")
    (project_dir / "final_script_state.json").write_text("{}", encoding="utf-8")

    response = client.post(f"/api/projects/{project_id}/reference/select", json={"video_id": "direct1"})

    assert response.status_code == 200
    assert not (project_dir / "candidates.json").exists()
    assert not (project_dir / "selected_script_candidate.json").exists()
    assert not (project_dir / "final_script.md").exists()
    assert not (project_dir / "final_script_state.json").exists()


def test_audio_upload_creates_reference_audio_file(tmp_path: Path):
    client = TestClient(create_app(repo_root=tmp_path, youtube_client_factory=FakeYouTubeClient))
    project_id = create_project(client)

    response = client.post(
        f"/api/projects/{project_id}/reference/audio/upload",
        files={"file": ("reference.wav", b"audio", "audio/wav")},
    )
    project = client.get(f"/api/projects/{project_id}").json()["project"]
    project_dir = tmp_path / "outputs" / project_id

    assert response.status_code == 200
    assert response.json()["audio_path"] == "reference_audio.wav"
    assert (project_dir / "reference_audio.wav").read_bytes() == b"audio"
    assert project["generated_files"]["reference_audio"] == "reference_audio.wav"


def test_audio_upload_rejects_empty_file(tmp_path: Path):
    client = TestClient(create_app(repo_root=tmp_path, youtube_client_factory=FakeYouTubeClient))
    project_id = create_project(client)

    response = client.post(
        f"/api/projects/{project_id}/reference/audio/upload",
        files={"file": ("reference.wav", b"", "audio/wav")},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Audio upload must not be empty"


def test_audio_upload_rejects_non_audio_file(tmp_path: Path):
    client = TestClient(create_app(repo_root=tmp_path, youtube_client_factory=FakeYouTubeClient))
    project_id = create_project(client)

    response = client.post(
        f"/api/projects/{project_id}/reference/audio/upload",
        files={"file": ("notes.txt", b"text", "text/plain")},
    )

    assert response.status_code == 400
    assert "Audio upload must be" in response.json()["detail"]


def test_audio_extract_requires_selected_reference(tmp_path: Path):
    client = TestClient(create_app(repo_root=tmp_path, youtube_client_factory=FakeYouTubeClient))
    project_id = create_project(client)

    response = client.post(f"/api/projects/{project_id}/reference/audio/extract")

    assert response.status_code == 400
    assert response.json()["detail"] == "Select a reference before extracting audio"


def test_audio_extract_creates_audio_file_and_succeeded_job(tmp_path: Path):
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "local.settings.json").write_text('{"youtube_api_key":"key"}', encoding="utf-8")
    client = TestClient(
        create_app(
            repo_root=tmp_path,
            youtube_client_factory=FakeYouTubeClient,
            audio_extractor=fake_audio_extractor,
        )
    )
    project_id = create_project(client)
    client.post(f"/api/projects/{project_id}/reference/search", json={"keyword": "돈"})
    client.post(f"/api/projects/{project_id}/reference/select", json={"video_id": "highratio1"})
    project_dir = tmp_path / "outputs" / project_id
    (project_dir / "reference_script.md").write_text("old script", encoding="utf-8")

    response = client.post(f"/api/projects/{project_id}/reference/audio/extract")
    project = client.get(f"/api/projects/{project_id}").json()["project"]
    restored = client.get(f"/api/projects/{project_id}/reference").json()

    assert response.status_code == 200
    assert response.json()["audio_path"] == "reference_audio.wav"
    assert (project_dir / "reference_audio.wav").read_bytes() == b"extracted audio"
    assert project["generated_files"]["reference_audio"] == "reference_audio.wav"
    assert project["job_history"][-1]["state"] == "succeeded"
    assert project["job_history"][-1]["output_paths"] == ["reference_audio.wav"]
    assert restored["reference_script"] is None


def test_audio_extract_missing_binary_marks_job_failed(tmp_path: Path):
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "local.settings.json").write_text(
        '{"youtube_api_key":"key","yt_dlp_binary":"/missing/yt-dlp"}',
        encoding="utf-8",
    )
    client = TestClient(create_app(repo_root=tmp_path, youtube_client_factory=FakeYouTubeClient))
    project_id = create_project(client)
    client.post(f"/api/projects/{project_id}/reference/search", json={"keyword": "돈"})
    client.post(f"/api/projects/{project_id}/reference/select", json={"video_id": "highratio1"})

    response = client.post(f"/api/projects/{project_id}/reference/audio/extract")
    project = client.get(f"/api/projects/{project_id}").json()["project"]

    assert response.status_code == 400
    assert "yt-dlp binary not found" in response.json()["detail"]
    assert project["job_history"][-1]["state"] == "failed"
    assert "yt-dlp binary not found" in project["job_history"][-1]["error_message"]


def test_audio_upload_clears_stale_stt_and_analysis_outputs(tmp_path: Path):
    client = TestClient(create_app(repo_root=tmp_path, youtube_client_factory=FakeYouTubeClient))
    project_id = create_project(client)
    project_dir = tmp_path / "outputs" / project_id
    (project_dir / "reference_raw_stt.json").write_text("{}", encoding="utf-8")
    (project_dir / "reference_script.md").write_text("old script", encoding="utf-8")
    (project_dir / "reference_analysis.json").write_text("{}", encoding="utf-8")
    (project_dir / "reference_analysis.md").write_text("old analysis", encoding="utf-8")

    response = client.post(
        f"/api/projects/{project_id}/reference/audio/upload",
        files={"file": ("reference.wav", b"new audio", "audio/wav")},
    )
    restored = client.get(f"/api/projects/{project_id}/reference").json()

    assert response.status_code == 200
    assert not (project_dir / "reference_raw_stt.json").exists()
    assert restored["reference_script"] is None
    assert restored["analysis"] is None
    assert restored["analysis_markdown"] is None


def test_audio_upload_replaces_previous_reference_audio_extension(tmp_path: Path):
    client = TestClient(create_app(repo_root=tmp_path, youtube_client_factory=FakeYouTubeClient))
    project_id = create_project(client)
    project_dir = tmp_path / "outputs" / project_id
    (project_dir / "reference_audio.wav").write_bytes(b"old audio")

    response = client.post(
        f"/api/projects/{project_id}/reference/audio/upload",
        files={"file": ("reference.mp3", b"new audio", "audio/mpeg")},
    )

    assert response.status_code == 200
    assert response.json()["audio_path"] == "reference_audio.mp3"
    assert not (project_dir / "reference_audio.wav").exists()
    assert (project_dir / "reference_audio.mp3").read_bytes() == b"new audio"


def test_reference_stt_endpoint_creates_script(tmp_path: Path):
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "local.settings.json").write_text('{"openai_api_key":"key"}', encoding="utf-8")
    client = TestClient(
        create_app(
            repo_root=tmp_path,
            youtube_client_factory=FakeYouTubeClient,
            transcription_client_factory=FakeTranscriptionClient,
        )
    )
    project_id = create_project(client)
    project_dir = tmp_path / "outputs" / project_id
    (project_dir / "reference_audio.wav").write_bytes(b"audio")

    response = client.post(f"/api/projects/{project_id}/reference/stt")
    project = client.get(f"/api/projects/{project_id}").json()["project"]

    assert response.status_code == 200
    assert response.json()["reference_script"] == "첫 문장입니다."
    assert (project_dir / "reference_raw_stt.json").exists()
    assert (project_dir / "reference_script.md").exists()
    assert project["generated_files"]["reference_raw_stt"] == "reference_raw_stt.json"
    assert project["generated_files"]["reference_script"] == "reference_script.md"
    assert project["current_step"] == "Analysis"
    assert step_state(project, "STT") == "succeeded"
    assert step_state(project, "Analysis") == "waiting"
    assert project["job_history"][-1]["state"] == "succeeded"


def test_reference_stt_rerun_clears_stale_analysis(tmp_path: Path):
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "local.settings.json").write_text('{"openai_api_key":"key"}', encoding="utf-8")
    client = TestClient(
        create_app(
            repo_root=tmp_path,
            youtube_client_factory=FakeYouTubeClient,
            transcription_client_factory=FakeTranscriptionClient,
        )
    )
    project_id = create_project(client)
    project_dir = tmp_path / "outputs" / project_id
    (project_dir / "reference_audio.wav").write_bytes(b"audio")
    (project_dir / "reference_analysis.json").write_text('{"old":true}', encoding="utf-8")
    (project_dir / "reference_analysis.md").write_text("old analysis", encoding="utf-8")

    response = client.post(f"/api/projects/{project_id}/reference/stt")
    state = client.get(f"/api/projects/{project_id}/reference").json()
    project = client.get(f"/api/projects/{project_id}").json()["project"]

    assert response.status_code == 200
    assert state["analysis"] is None
    assert state["analysis_markdown"] is None
    assert "reference_analysis" not in project["generated_files"]


def test_reference_stt_uses_uploaded_audio_extension(tmp_path: Path):
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "local.settings.json").write_text('{"openai_api_key":"key"}', encoding="utf-8")
    client = TestClient(
        create_app(
            repo_root=tmp_path,
            youtube_client_factory=FakeYouTubeClient,
            transcription_client_factory=FakeTranscriptionClient,
        )
    )
    project_id = create_project(client)
    client.post(
        f"/api/projects/{project_id}/reference/audio/upload",
        files={"file": ("reference.mp3", b"audio", "audio/mpeg")},
    )

    response = client.post(f"/api/projects/{project_id}/reference/stt")
    project = client.get(f"/api/projects/{project_id}").json()["project"]

    assert response.status_code == 200
    assert project["job_history"][-1]["input_paths"] == ["reference_audio.mp3"]


def test_reference_stt_auto_extracts_selected_reference_audio_when_missing(tmp_path: Path):
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "local.settings.json").write_text(
        '{"youtube_api_key":"key","openai_api_key":"key"}',
        encoding="utf-8",
    )
    client = TestClient(
        create_app(
            repo_root=tmp_path,
            youtube_client_factory=FakeYouTubeClient,
            audio_extractor=fake_audio_extractor,
            transcription_client_factory=FakeTranscriptionClient,
        )
    )
    project_id = create_project(client)
    client.post(f"/api/projects/{project_id}/reference/search", json={"keyword": "돈"})
    client.post(f"/api/projects/{project_id}/reference/select", json={"video_id": "highratio1"})

    response = client.post(f"/api/projects/{project_id}/reference/stt")
    project = client.get(f"/api/projects/{project_id}").json()["project"]
    project_dir = tmp_path / "outputs" / project_id

    assert response.status_code == 200
    assert (project_dir / "reference_audio.wav").read_bytes() == b"extracted audio"
    assert project["generated_files"]["reference_audio"] == "reference_audio.wav"
    assert project["generated_files"]["reference_script"] == "reference_script.md"
    assert [job["job_type"] for job in project["job_history"][-2:]] == [
        "reference_audio_extract",
        "reference_stt",
    ]
    assert step_state(project, "STT") == "succeeded"


def test_reference_stt_requires_audio_file(tmp_path: Path):
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "local.settings.json").write_text('{"openai_api_key":"key"}', encoding="utf-8")
    client = TestClient(
        create_app(
            repo_root=tmp_path,
            youtube_client_factory=FakeYouTubeClient,
            transcription_client_factory=FakeTranscriptionClient,
        )
    )
    project_id = create_project(client)

    response = client.post(f"/api/projects/{project_id}/reference/stt")

    assert response.status_code == 400
    assert response.json()["detail"] == "Reference audio is missing"


def test_reference_stt_failing_provider_marks_job_failed(tmp_path: Path):
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "local.settings.json").write_text('{"openai_api_key":"key"}', encoding="utf-8")
    client = TestClient(
        create_app(
            repo_root=tmp_path,
            youtube_client_factory=FakeYouTubeClient,
            transcription_client_factory=FailingTranscriptionClient,
        )
    )
    project_id = create_project(client)
    project_dir = tmp_path / "outputs" / project_id
    (project_dir / "reference_audio.wav").write_bytes(b"audio")

    response = client.post(f"/api/projects/{project_id}/reference/stt")
    project = client.get(f"/api/projects/{project_id}").json()["project"]

    assert response.status_code == 400
    assert "openai unavailable" in response.json()["detail"]
    assert project["job_history"][-1]["state"] == "failed"
    assert "openai unavailable" in project["job_history"][-1]["error_message"]
    assert "reference_raw_stt" not in project["generated_files"]


def test_reference_stt_does_not_fallback_when_recorded_audio_is_missing(tmp_path: Path):
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "local.settings.json").write_text('{"openai_api_key":"key"}', encoding="utf-8")
    client = TestClient(
        create_app(
            repo_root=tmp_path,
            youtube_client_factory=FakeYouTubeClient,
            transcription_client_factory=FakeTranscriptionClient,
        )
    )
    project_id = create_project(client)
    project_dir = tmp_path / "outputs" / project_id
    client.post(
        f"/api/projects/{project_id}/reference/audio/upload",
        files={"file": ("reference.mp3", b"audio", "audio/mpeg")},
    )
    (project_dir / "reference_audio.mp3").unlink()
    (project_dir / "reference_audio.wav").write_bytes(b"stale audio")

    response = client.post(f"/api/projects/{project_id}/reference/stt")
    project = client.get(f"/api/projects/{project_id}").json()["project"]

    assert response.status_code == 400
    assert response.json()["detail"] == "Reference audio is missing"
    assert not project["job_history"] or project["job_history"][-1]["job_type"] != "reference_stt"


def test_reference_analysis_endpoint_creates_report(tmp_path: Path):
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "local.settings.json").write_text('{"openai_api_key":"key"}', encoding="utf-8")
    client = TestClient(
        create_app(
            repo_root=tmp_path,
            youtube_client_factory=FakeYouTubeClient,
            analysis_client_factory=FakeAnalysisClient,
        )
    )
    project_id = create_project(client)
    project_dir = tmp_path / "outputs" / project_id
    (project_dir / "reference_script.md").write_text("이걸 모르면 손해입니다.", encoding="utf-8")

    response = client.post(f"/api/projects/{project_id}/reference/analyze")
    state = client.get(f"/api/projects/{project_id}/reference").json()
    project = client.get(f"/api/projects/{project_id}").json()["project"]

    assert response.status_code == 200
    assert response.json()["analysis"]["primary_structure"] == "common-sense conflict"
    assert "Reference Analysis" in state["analysis_markdown"]
    assert (project_dir / "reference_analysis.json").exists()
    assert (project_dir / "reference_analysis.md").exists()
    assert project["generated_files"]["reference_analysis"] == "reference_analysis.json"
    assert project["generated_files"]["reference_analysis_markdown"] == "reference_analysis.md"
    assert project["current_step"] == "Candidates"
    assert step_state(project, "Analysis") == "succeeded"
    assert step_state(project, "Candidates") == "waiting"
    assert project["job_history"][-1]["state"] == "succeeded"


def test_reference_analysis_requires_script(tmp_path: Path):
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "local.settings.json").write_text('{"openai_api_key":"key"}', encoding="utf-8")
    client = TestClient(
        create_app(
            repo_root=tmp_path,
            youtube_client_factory=FakeYouTubeClient,
            analysis_client_factory=FakeAnalysisClient,
        )
    )
    project_id = create_project(client)

    response = client.post(f"/api/projects/{project_id}/reference/analyze")

    assert response.status_code == 400
    assert response.json()["detail"] == "Reference script is missing"


def test_reference_analysis_failing_provider_marks_job_failed(tmp_path: Path):
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "local.settings.json").write_text('{"openai_api_key":"key"}', encoding="utf-8")
    client = TestClient(
        create_app(
            repo_root=tmp_path,
            youtube_client_factory=FakeYouTubeClient,
            analysis_client_factory=FailingAnalysisClient,
        )
    )
    project_id = create_project(client)
    project_dir = tmp_path / "outputs" / project_id
    (project_dir / "reference_script.md").write_text("이걸 모르면 손해입니다.", encoding="utf-8")

    response = client.post(f"/api/projects/{project_id}/reference/analyze")
    project = client.get(f"/api/projects/{project_id}").json()["project"]

    assert response.status_code == 400
    assert "analysis unavailable" in response.json()["detail"]
    assert project["job_history"][-1]["state"] == "failed"
    assert "analysis unavailable" in project["job_history"][-1]["error_message"]
    assert "reference_analysis" not in project["generated_files"]


def test_reference_analysis_failed_rerun_clears_stale_analysis(tmp_path: Path):
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "local.settings.json").write_text('{"openai_api_key":"key"}', encoding="utf-8")
    success_client = TestClient(
        create_app(
            repo_root=tmp_path,
            youtube_client_factory=FakeYouTubeClient,
            analysis_client_factory=FakeAnalysisClient,
        )
    )
    project_id = create_project(success_client)
    project_dir = tmp_path / "outputs" / project_id
    (project_dir / "reference_script.md").write_text("이걸 모르면 손해입니다.", encoding="utf-8")
    assert success_client.post(f"/api/projects/{project_id}/reference/analyze").status_code == 200

    failing_client = TestClient(
        create_app(
            repo_root=tmp_path,
            youtube_client_factory=FakeYouTubeClient,
            analysis_client_factory=FailingAnalysisClient,
        )
    )

    response = failing_client.post(f"/api/projects/{project_id}/reference/analyze")
    state = failing_client.get(f"/api/projects/{project_id}/reference").json()
    project = failing_client.get(f"/api/projects/{project_id}").json()["project"]

    assert response.status_code == 400
    assert state["analysis"] is None
    assert state["analysis_markdown"] is None
    assert project["current_step"] == "Analysis"
    assert step_state(project, "Analysis") == "failed"
    assert "reference_analysis" not in project["generated_files"]


def test_reference_analysis_rejects_invalid_payload(tmp_path: Path):
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "local.settings.json").write_text('{"openai_api_key":"key"}', encoding="utf-8")
    client = TestClient(
        create_app(
            repo_root=tmp_path,
            youtube_client_factory=FakeYouTubeClient,
            analysis_client_factory=InvalidAnalysisClient,
        )
    )
    project_id = create_project(client)
    project_dir = tmp_path / "outputs" / project_id
    (project_dir / "reference_script.md").write_text("이걸 모르면 손해입니다.", encoding="utf-8")

    response = client.post(f"/api/projects/{project_id}/reference/analyze")
    project = client.get(f"/api/projects/{project_id}").json()["project"]

    assert response.status_code == 400
    assert "Field required" in response.json()["detail"]
    assert project["job_history"][-1]["state"] == "failed"
