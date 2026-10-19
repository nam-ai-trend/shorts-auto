from pathlib import Path

from fastapi.testclient import TestClient

from app.main import create_app


class FakeScriptClient:
    def __init__(self, api_key: str, model: str):
        self.api_key = api_key
        self.model = model

    def analyze(self, prompt: str):
        if "system instruction: generate" in prompt.lower() or ("candidates" in prompt.lower() and "draft" in prompt.lower() and "selected candidate" not in prompt.lower()):
            return {
                "candidates": [
                    {
                        "candidate_id": "same-topic-1",
                        "candidate_type": "same_topic",
                        "title": "같은 주제 리메이크",
                        "hook": "돈을 못 모으는 사람은 이것부터 틀립니다.",
                        "target_viewer": "사회초년생",
                        "why_it_can_work": "자기 문제처럼 들리는 훅입니다.",
                        "main_curiosity_question": "왜 돈이 안 모일까?",
                        "structure_summary": "상식 반박, 원인, 반전, 결론.",
                        "draft_script": "돈을 못 모으는 사람은 의지가 약한 게 아닙니다. 기준이 잘못됐습니다.",
                        "borrowed_reference_structure": "레퍼런스의 상식 반박 구조를 빌립니다.",
                    },
                    {
                        "candidate_id": "different-topic-1",
                        "candidate_type": "different_topic",
                        "title": "잠을 망치는 습관",
                        "hook": "잠을 못 자는 사람은 밤이 아니라 아침을 망칩니다.",
                        "target_viewer": "수면이 부족한 직장인",
                        "why_it_can_work": "예상과 다른 원인이 궁금증을 만듭니다.",
                        "main_curiosity_question": "왜 아침 습관이 잠을 망칠까?",
                        "structure_summary": "오해 제시, 원인 이동, 반전, 해결.",
                        "draft_script": "잠을 못 자는 사람은 밤에만 문제가 있는 게 아닙니다. 아침 첫 행동이 밤을 결정합니다.",
                        "borrowed_reference_structure": "원인 이동 구조를 빌립니다.",
                    },
                    {
                        "candidate_id": "different-topic-2",
                        "candidate_type": "different_topic",
                        "title": "집중력을 잃는 이유",
                        "hook": "집중력이 없는 게 아니라 시작 방식이 틀렸습니다.",
                        "target_viewer": "일을 미루는 사람",
                        "why_it_can_work": "책임감을 덜어주면서 답을 기다리게 합니다.",
                        "main_curiosity_question": "왜 시작 방식이 집중력을 망칠까?",
                        "structure_summary": "자책 해소, 원인 제시, 반전, 결론.",
                        "draft_script": "집중력이 없는 사람은 대부분 게으른 게 아닙니다. 시작을 너무 크게 잡습니다.",
                        "borrowed_reference_structure": "자책 해소형 훅을 빌립니다.",
                    },
                    {
                        "candidate_id": "different-topic-3",
                        "candidate_type": "different_topic",
                        "title": "관계가 피곤한 이유",
                        "hook": "사람이 싫은 게 아니라 대화 순서가 틀렸습니다.",
                        "target_viewer": "인간관계에 지친 사람",
                        "why_it_can_work": "감정 문제를 구조 문제로 바꿉니다.",
                        "main_curiosity_question": "왜 대화 순서가 관계를 망칠까?",
                        "structure_summary": "공감, 원인 전환, 예시, 결론.",
                        "draft_script": "사람이 싫어진 줄 알았는데 사실은 매번 같은 순서로 지치는 겁니다.",
                        "borrowed_reference_structure": "감정 문제를 구조 문제로 바꾸는 방식을 빌립니다.",
                    },
                ]
            }
        return {
            "final_script": "잠을 못 자는 이유는 밤이 아니라 아침에 있습니다. 첫 행동을 바꾸면 밤이 달라집니다."
        }


class FailingScriptClient:
    def __init__(self, api_key: str, model: str):
        self.api_key = api_key
        self.model = model

    def analyze(self, prompt: str):
        raise RuntimeError("openai unavailable")


def create_project(client: TestClient) -> str:
    return client.post("/api/projects", json={"project_title": "대본"}).json()["project"][
        "project_id"
    ]


def step_state(project: dict, step_name: str) -> str:
    return next(step["state"] for step in project["step_statuses"] if step["name"] == step_name)


def write_reference_inputs(project_dir: Path) -> None:
    (project_dir / "reference_script.md").write_text("레퍼런스 대본", encoding="utf-8")
    (project_dir / "reference_analysis.json").write_text(
        '{"primary_structure":"상식 반박","supporting_structures":[],"hook_analysis":"훅","curiosity_gap":"궁금증","retention_analysis":"유지","payoff_analysis":"보상","risk_notes":[],"reusable_structure_notes":"구조","section_breakdown":[]}',
        encoding="utf-8",
    )


def test_scripts_state_defaults_empty(tmp_path: Path):
    client = TestClient(create_app(repo_root=tmp_path, analysis_client_factory=FakeScriptClient))
    project_id = create_project(client)

    response = client.get(f"/api/projects/{project_id}/scripts")

    assert response.status_code == 200
    assert response.json()["candidates"] == []
    assert response.json()["selected_candidate"] is None
    assert response.json()["final_script"] is None


def test_generate_select_and_finalize_script(tmp_path: Path):
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "local.settings.json").write_text('{"openai_api_key":"key"}', encoding="utf-8")
    client = TestClient(create_app(repo_root=tmp_path, analysis_client_factory=FakeScriptClient))
    project_id = create_project(client)
    project_dir = tmp_path / "outputs" / project_id
    write_reference_inputs(project_dir)

    generated = client.post(f"/api/projects/{project_id}/scripts/candidates")
    selected = client.post(
        f"/api/projects/{project_id}/scripts/select",
        json={"candidate_id": "different-topic-1"},
    )
    finalized = client.post(
        f"/api/projects/{project_id}/scripts/finalize",
        json={"feedback": "더 짧고 강하게"},
    )
    state = client.get(f"/api/projects/{project_id}/scripts").json()
    project = client.get(f"/api/projects/{project_id}").json()["project"]

    assert generated.status_code == 200
    assert len(generated.json()["candidates"]) == 4
    assert selected.status_code == 200
    assert selected.json()["selected_candidate"]["candidate_id"] == "different-topic-1"
    assert finalized.status_code == 200
    assert "아침" in finalized.json()["final_script"]
    assert state["final_script"] == finalized.json()["final_script"]
    assert (project_dir / "candidates.json").exists()
    assert (project_dir / "selected_script_candidate.json").exists()
    assert (project_dir / "final_script.md").exists()
    assert project["generated_files"]["script_candidates"] == "candidates.json"
    assert project["generated_files"]["final_script"] == "final_script.md"
    assert project["current_step"] == "Production"
    assert step_state(project, "Candidates") == "succeeded"
    assert step_state(project, "Script") == "succeeded"


def test_generate_candidates_requires_analysis(tmp_path: Path):
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "local.settings.json").write_text('{"openai_api_key":"key"}', encoding="utf-8")
    client = TestClient(create_app(repo_root=tmp_path, analysis_client_factory=FakeScriptClient))
    project_id = create_project(client)

    response = client.post(f"/api/projects/{project_id}/scripts/candidates")

    assert response.status_code == 400
    assert response.json()["detail"] == "Reference script and analysis are required"


def test_finalize_requires_selected_candidate(tmp_path: Path):
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "local.settings.json").write_text('{"openai_api_key":"key"}', encoding="utf-8")
    client = TestClient(create_app(repo_root=tmp_path, analysis_client_factory=FakeScriptClient))
    project_id = create_project(client)

    response = client.post(f"/api/projects/{project_id}/scripts/finalize", json={"feedback": ""})

    assert response.status_code == 400
    assert response.json()["detail"] == "Select a script candidate before finalizing"


def test_generate_failure_marks_job_failed(tmp_path: Path):
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "local.settings.json").write_text('{"openai_api_key":"key"}', encoding="utf-8")
    client = TestClient(create_app(repo_root=tmp_path, analysis_client_factory=FailingScriptClient))
    project_id = create_project(client)
    write_reference_inputs(tmp_path / "outputs" / project_id)

    response = client.post(f"/api/projects/{project_id}/scripts/candidates")
    project = client.get(f"/api/projects/{project_id}").json()["project"]

    assert response.status_code == 400
    assert "openai unavailable" in response.json()["detail"]
    assert project["job_history"][-1]["state"] == "failed"
