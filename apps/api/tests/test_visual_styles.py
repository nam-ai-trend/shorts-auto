import json
from pathlib import Path
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

from app.main import create_app
from app.projects.service import create_project
from app.production.visual_styles import VISUAL_STYLES, get_visual_style


def test_visual_styles_catalog_and_update(tmp_path: Path):
    app = create_app(repo_root=tmp_path)
    client = TestClient(app)

    outputs_dir = tmp_path / "outputs"
    project = create_project(outputs_dir, project_title="스타일 테스트", now="261016_1200")
    project_id = project.project_id
    proj_dir = outputs_dir / project_id

    # 1. 10대 비주얼 스타일 카탈로그 조회
    resp = client.get(f"/api/projects/{project_id}/production/visual-styles")
    assert resp.status_code == 200
    styles = resp.json()
    assert len(styles) == 10

    # 번호 및 스타일명 검증
    style_names = [s["name"] for s in styles]
    assert any("실사형" in name for name in style_names)
    assert any("시네마틱" in name for name in style_names)
    assert any("2D 카툰" in name for name in style_names)
    assert any("일본 애니" in name for name in style_names)
    assert any("3D 애니메이션" in name for name in style_names)
    assert any("모션그래픽" in name for name in style_names)
    assert any("키네틱 타이포그래피" in name for name in style_names)
    assert any("클레이 애니메이션" in name for name in style_names)
    assert any("스크린캐스트" in name for name in style_names)
    assert any("믹스드 미디어" in name for name in style_names)

    # 2. 스타일별 특징 및 어울리는 콘텐츠 검증
    live_action = next(s for s in styles if s["id"] == "live_action")
    assert "과학 현상, 실험, 자연, 역사" in live_action["best_for"]
    assert "실제 사람, 사물, 배경을 촬영" in live_action["feature"]

    # 3. 스타일 업데이트 엔드포인트 테스트
    update_resp = client.post(
        f"/api/projects/{project_id}/production/visual-style",
        json={"visual_style_id": "cinematic", "regenerate_prompts": False}
    )
    assert update_resp.status_code == 200
    update_data = update_resp.json()
    assert update_data["concept_kit"]["visual_style_id"] == "cinematic"
    assert "cinematic" in update_data["concept_kit"]["visual_style"].lower()

