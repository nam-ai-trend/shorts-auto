import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import create_app


from app.projects.service import create_project


def test_production_state_and_assets(tmp_path: Path):
    app = create_app(repo_root=tmp_path)
    client = TestClient(app)

    outputs_dir = tmp_path / "outputs"
    project = create_project(outputs_dir, project_title="테스트 쇼츠", now="261016_1200")
    project_id = project.project_id

    # 2. production 초기 상태 조회
    resp = client.get(f"/api/projects/{project_id}/production")
    assert resp.status_code == 200
    data = resp.json()
    assert data["has_audio"] is False
    assert data["has_video_scenes"] is False

    # 3. video_scenes.json 및 scene 파일 준비
    proj_dir = outputs_dir / project_id
    scenes_dir = proj_dir / "scenes"
    scenes_dir.mkdir(parents=True, exist_ok=True)

    dummy_video_scenes = [
        {
            "scene_id": 1,
            "target_duration": 5.0,
            "start": 0.0,
            "end": 5.0,
            "duration_frames": 150,
            "narration": "첫 번째 씬 나레이션",
            "start_image_prompt": "Prompt 1",
            "video_prompt": "Motion 1",
            "continuity": {
                "camera": "Eye-level",
                "subject_state": "Hero",
                "lighting": "Studio",
                "handoff_description": "Smooth tilt up",
            },
            "is_locked": False,
        },
        {
            "scene_id": 2,
            "target_duration": 5.0,
            "start": 5.0,
            "end": 10.0,
            "duration_frames": 150,
            "narration": "두 번째 씬 나레이션",
            "start_image_prompt": "Prompt 2",
            "video_prompt": "Motion 2",
            "continuity": {
                "camera": "Top-down",
                "subject_state": "Tree",
                "lighting": "Sunlight",
                "handoff_description": "Pan to ground",
            },
            "is_locked": False,
        },
    ]
    (proj_dir / "video_scenes.json").write_text(json.dumps(dummy_video_scenes), encoding="utf-8")

    # 더미 mp4 파일 및 final png 생성
    mp4_path = scenes_dir / "scene_01_video.mp4"
    mp4_path.write_bytes(b"\x00\x00\x00\x20ftypisom")
    final_png = scenes_dir / "scene_01_final.png"
    final_png.write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR")

    # 4. mp4 서빙 테스트
    resp = client.get(f"/api/projects/{project_id}/production/scenes/scene_01_video.mp4")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "video/mp4"

    # 5. 다음 씬으로 프레임 인계 테스트 (POST /scenes/1/pass-next)
    resp = client.post(f"/api/projects/{project_id}/production/scenes/1/pass-next")
    assert resp.status_code == 200
    # scene_02_start.png가 생성되었는지 확인
    next_start = scenes_dir / "scene_02_start.png"
    assert next_start.exists()
    assert next_start.read_bytes() == final_png.read_bytes()

    # 6. state 조회 시 URL 바인딩 확인
    resp = client.get(f"/api/projects/{project_id}/production")
    assert resp.status_code == 200
    state = resp.json()
    assert state["video_scene_count"] == 2
    sc1 = state["video_scenes"][0]
    sc2 = state["video_scenes"][1]
    assert sc1["generated_video_url"] == f"/api/projects/{project_id}/production/scenes/scene_01_video.mp4"
    assert sc1["final_frame_url"] == f"/api/projects/{project_id}/production/scenes/scene_01_final.png"
    assert sc2["start_image_url"] == f"/api/projects/{project_id}/production/scenes/scene_02_start.png"
    assert sc2["continuity"]["prev_final_frame_url"] == sc1["final_frame_url"]
