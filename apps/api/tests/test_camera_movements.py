import json
from pathlib import Path
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

from app.core.settings import AppSettings
from app.main import create_app
from app.projects.service import create_project


def test_camera_movements_api_and_recommendation(tmp_path: Path):
    app = create_app(repo_root=tmp_path)
    client = TestClient(app)

    outputs_dir = tmp_path / "outputs"
    project = create_project(outputs_dir, project_title="모션 테스트", now="261016_1200")
    project_id = project.project_id
    proj_dir = outputs_dir / project_id

    # 1. 12대 카메라 모션 카탈로그 조회
    resp = client.get(f"/api/projects/{project_id}/production/camera-movements")
    assert resp.status_code == 200
    movements = resp.json()
    assert len(movements) == 12
    ids = [m["id"] for m in movements]
    assert "crash_zoom_in" in ids
    assert "whip_pan" in ids
    assert "orbit" in ids
    assert "push_past" in ids

    # 2. video_scenes.json 준비
    dummy_video_scenes = [
        {
            "scene_id": 1,
            "target_duration": 5.0,
            "start": 0.0,
            "end": 5.0,
            "duration_frames": 150,
            "narration": "기껏해야 얼마 안 되겠지 생각하겠지만, 이거 완전 아닙니다!",
            "start_image_prompt": "Claymation scene 1, tiny character surprised",
            "video_prompt": "camera: slow dolly in. movement: slowly advance.",
            "camera_movement": "slow_zoom_in",
            "continuity": {
                "camera": "Eye-level",
                "subject_state": "Initial",
                "lighting": "Studio",
                "handoff_description": "Handoff",
            },
            "is_locked": False,
        }
    ]
    (proj_dir / "video_scenes.json").write_text(
        json.dumps(dummy_video_scenes, ensure_ascii=False), encoding="utf-8"
    )

    # 3. Fallback 모션 추천 테스트 (OpenAI 키가 없을 때)
    rec_resp = client.post(f"/api/projects/{project_id}/production/scenes/1/recommend-motion")
    assert rec_resp.status_code == 200
    rec_data = rec_resp.json()
    assert rec_data["scene_id"] == 1
    assert len(rec_data["recommendations"]) >= 1
    assert rec_data["recommendations"][0]["movement_id"] == "crash_zoom_in"
    assert "후킹" in rec_data["recommendations"][0]["reason"]

    # 4. 모션 적용 엔드포인트 테스트 (모션 적용 시 video_prompt 및 camera_movement 갱신)
    apply_resp = client.post(
        f"/api/projects/{project_id}/production/scenes/1/apply-motion",
        json={"movement_id": "crash_zoom_in", "custom_instruction": "캐릭터 얼굴 표정을 더욱 극적으로 클로즈업해줘"},
    )
    assert apply_resp.status_code == 200
    applied_data = apply_resp.json()
    assert applied_data["scene"]["camera_movement"] == "crash_zoom_in"
    assert "crash zoom in" in applied_data["scene"]["video_prompt"]

    # 5. production 전체 상태에 반영 확인
    assert applied_data["production"]["video_scenes"][0]["camera_movement"] == "crash_zoom_in"
