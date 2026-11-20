import json
from pathlib import Path
from unittest.mock import patch

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


def test_production_thumbnail_endpoints(tmp_path: Path):
    app = create_app(repo_root=tmp_path)
    client = TestClient(app)

    outputs_dir = tmp_path / "outputs"
    project = create_project(outputs_dir, project_title="썸네일 테스트", now="261016_1300")
    project_id = project.project_id

    # 1. 썸네일 업로드
    file_content = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR_THUMBNAIL_BYTES"
    files = {"file": ("thumb.png", file_content, "image/png")}
    resp = client.post(f"/api/projects/{project_id}/production/thumbnail", files=files)
    assert resp.status_code == 200
    data = resp.json()
    assert data["has_thumbnail"] is True
    assert data["thumbnail_url"] == f"/api/projects/{project_id}/production/thumbnail"

    # 2. 썸네일 이미지 조회
    resp = client.get(f"/api/projects/{project_id}/production/thumbnail")
    assert resp.status_code == 200
    assert resp.content == file_content
    assert "no-cache" in resp.headers.get("Cache-Control", "")

    # 3. 썸네일 삭제
    resp = client.delete(f"/api/projects/{project_id}/production/thumbnail")
    assert resp.status_code == 200
    data = resp.json()
    assert data["has_thumbnail"] is False
    assert data["thumbnail_url"] is None

    # 4. 씬 1 이미지로부터 썸네일 설정
    scenes_dir = outputs_dir / project_id / "scenes"
    scenes_dir.mkdir(parents=True, exist_ok=True)
    (scenes_dir / "scene_01_start.png").write_bytes(b"SCENE_1_START_IMAGE")
    resp = client.post(f"/api/projects/{project_id}/production/thumbnail/from-scene", json={"scene_id": 1})
    assert resp.status_code == 200
    assert resp.json()["has_thumbnail"] is True
    resp = client.get(f"/api/projects/{project_id}/production/thumbnail")
    assert resp.status_code == 200
    assert resp.content == b"SCENE_1_START_IMAGE"


@patch("app.production.router.render_final_shorts")
def test_thumbnail_from_scene_triggers_auto_render_when_final_video_exists(mock_render, tmp_path: Path):
    app = create_app(repo_root=tmp_path)
    client = TestClient(app)

    outputs_dir = tmp_path / "outputs"
    project = create_project(outputs_dir, project_title="자동 렌더링 테스트", now="261016_1400")
    project_id = project.project_id
    proj_dir = outputs_dir / project_id

    # final.mp4 파일 및 scene_01_start.png 파일 준비
    (proj_dir / "final.mp4").write_bytes(b"dummy_final_video")
    scenes_dir = proj_dir / "scenes"
    scenes_dir.mkdir(parents=True, exist_ok=True)
    (scenes_dir / "scene_01_start.png").write_bytes(b"SCENE_1_START_IMAGE")

    resp = client.post(f"/api/projects/{project_id}/production/thumbnail/from-scene", json={"scene_id": 1})
    assert resp.status_code == 200
    assert resp.json()["has_thumbnail"] is True
    # final.mp4가 있었으므로 render_final_shorts가 자동 호출되어야 함
    assert mock_render.called
    assert mock_render.call_args[0][0] == proj_dir


def test_resolve_project_shorts_title_fallback(tmp_path: Path):
    from app.production.renderer import resolve_project_shorts_title

    pdir = tmp_path / "test_proj"
    pdir.mkdir(parents=True, exist_ok=True)

    # 1. 인자로 넘긴 명시적 타이틀 우선
    assert resolve_project_shorts_title(pdir, "명시적 제목") == "명시적 제목"

    # 2. project.json의 project_title
    (pdir / "project.json").write_text(json.dumps({"project_title": "프로젝트 제목"}), encoding="utf-8")
    assert resolve_project_shorts_title(pdir, None) == "프로젝트 제목"
    assert resolve_project_shorts_title(pdir, "untitled") == "프로젝트 제목"

    # 3. project.json이 untitled일 때 selected_script_candidate.json 확인
    (pdir / "project.json").write_text(json.dumps({"project_title": "untitled"}), encoding="utf-8")
    (pdir / "selected_script_candidate.json").write_text(json.dumps({"title": "선택된 초안 제목"}), encoding="utf-8")
    assert resolve_project_shorts_title(pdir, None) == "선택된 초안 제목"

    # 4. candidates.json 확인
    (pdir / "selected_script_candidate.json").unlink()
    (pdir / "candidates.json").write_text(json.dumps([{"title": "후보군 1번 제목"}]), encoding="utf-8")
    assert resolve_project_shorts_title(pdir, None) == "후보군 1번 제목"

    # 5. display_script.md 첫 문장 후킹 확인
    (pdir / "candidates.json").unlink()
    (pdir / "display_script.md").write_text("수백만 원짜리 천연 진주를 반으로 쪼개면, 벌레가 나옵니다.", encoding="utf-8")
    assert resolve_project_shorts_title(pdir, None) == "수백만 원짜리 천연 진주를 반으로 쪼개면"


def test_asset_sheet_generation_and_serving(tmp_path: Path):
    app = create_app(repo_root=tmp_path)
    client = TestClient(app)

    outputs_dir = tmp_path / "outputs"
    project = create_project(outputs_dir, project_title="에셋시트 테스트", now="261016_1500")
    project_id = project.project_id
    proj_dir = outputs_dir / project_id

    # 컨셉 키트 파일 생성
    concept_kit_data = {
        "visual_style_id": "claymation",
        "visual_style": "Cute handcrafted miniature claymation",
        "color_and_lighting": "Warm sunlight",
        "core_objects": ["폐 모형", "공기 방울"],
        "camera_composition": "Close-up",
        "continuity_rules": ["Keep character scale"],
        "character_definition": {
            "name": "클레이 박사",
            "description": "귀여운 점토 인형 박사 캐릭터",
            "key_features": ["흰색 가운", "둥근 안경"]
        },
        "key_props": [
            {"name": "인체 폐 모형", "description": "점토로 빚은 정밀 허파꽈리 모형"},
            {"name": "2L 생수병", "description": "파란색 뚜껑이 있는 투명 생수병 10개 묶음"}
        ],
        "master_asset_sheet_prompt": "Test master asset sheet prompt"
    }
    (proj_dir / "concept_kit.json").write_text(json.dumps(concept_kit_data), encoding="utf-8")

    # 1. 초기 에셋 시트 조회 (None)
    resp = client.get(f"/api/projects/{project_id}/production/asset-sheet")
    assert resp.status_code == 200
    assert resp.json()["asset_sheet"] is None

    # 2. 에셋 시트 생성 API 호출 (POST /asset-sheet) - CLI 호출 대신 fallback 템플릿 제너레이터 실행되도록 mock
    with patch("app.production.service._run_higgsfield_generate", side_effect=RuntimeError("Test mock fallback")):
        resp = client.post(f"/api/projects/{project_id}/production/asset-sheet", json={"model": "nano_banana_pro"})
        assert resp.status_code == 200
        sheet = resp.json()
    assert sheet["has_sheet"] is True
    assert sheet["character_name"] == "클레이 박사"
    assert sheet["prop_1_name"] == "인체 폐 모형"
    assert sheet["prop_2_name"] == "2L 생수병"
    assert "master_asset_sheet.png" in sheet["master_sheet_url"]
    assert "master_character.png" in sheet["character_url"]
    assert "prop_1.png" in sheet["prop_1_url"]
    assert "prop_2.png" in sheet["prop_2_url"]

    # 3. 디스크에 실제 3개 분할 에셋 및 마스터 시트가 생성되었는지 확인
    assets_dir = proj_dir / "assets"
    assert (assets_dir / "master_asset_sheet.png").exists()
    assert (assets_dir / "master_character.png").exists()
    assert (assets_dir / "prop_1.png").exists()
    assert (assets_dir / "prop_2.png").exists()
    assert (assets_dir / "asset_sheet_manifest.json").exists()

    # 4. 정적 에셋 서빙 API 테스트 (GET /assets/{filename})
    resp = client.get(f"/api/projects/{project_id}/production/assets/master_character.png")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "image/png"

    resp = client.get(f"/api/projects/{project_id}/production/assets/prop_1.png")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "image/png"

    # 5. Production 상태 조회 시 asset_sheet 포함 여부 확인
    resp = client.get(f"/api/projects/{project_id}/production")
    assert resp.status_code == 200
    prod_data = resp.json()
    assert prod_data.get("asset_sheet") is not None
    assert prod_data["asset_sheet"]["has_sheet"] is True
    assert prod_data["asset_sheet"]["character_name"] == "클레이 박사"


