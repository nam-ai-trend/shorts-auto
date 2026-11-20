import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.core.settings import AppSettings
from app.production.service import (
    FLOW_IMAGE_MODELS,
    FLOW_VIDEO_MODELS,
    _acquire_flow_profile,
    _run_flow_image_generate,
    _run_flow_video_generate,
    generate_scene_image_for_project,
    generate_scene_video_for_project,
    get_flow_worker_count,
)


def test_flow_models_mapping():
    assert "flow_nano_pro" in FLOW_IMAGE_MODELS
    assert FLOW_IMAGE_MODELS["flow_nano_pro"] == "nano-pro"
    assert FLOW_IMAGE_MODELS["flow_imagen_4"] == "imagen4"

    assert "flow_veo_fast" in FLOW_VIDEO_MODELS
    assert FLOW_VIDEO_MODELS["flow_veo_fast"] == "veo-fast"
    assert FLOW_VIDEO_MODELS["flow_omni_flash"] == "omni-flash"


@patch("subprocess.run")
@patch("shutil.which")
def test_run_flow_image_generate(mock_which, mock_run, tmp_path):
    mock_which.return_value = "/mock/bin/gflow"
    out_file = tmp_path / "out.png"

    # subprocess가 파일을 생성하도록 side_effect 설정
    def fake_run(cmd, **kwargs):
        out_file.write_bytes(b"dummy_image_data_1234567890")
        res = MagicMock()
        res.returncode = 0
        res.stdout = "{}"
        res.stderr = ""
        return res

    mock_run.side_effect = fake_run

    res = _run_flow_image_generate(
        model_alias="nano-pro",
        prompt="A cute miniature clay robot",
        output_path=out_file,
        aspect_ratio="9:16",
    )

    assert res == out_file
    assert mock_run.called
    first_cmd = mock_run.call_args_list[0][0][0]
    assert first_cmd[0] == "/mock/bin/gflow"
    assert "image" in first_cmd
    assert "t2i" in first_cmd
    assert "--model" in first_cmd
    assert "nano-pro" in first_cmd
    assert "--aspect" in first_cmd
    assert "9:16" in first_cmd


@patch("subprocess.run")
@patch("shutil.which")
def test_run_flow_image_generate_with_references(mock_which, mock_run, tmp_path):
    mock_which.return_value = "/mock/bin/gflow"
    out_file = tmp_path / "out.png"
    ref1 = tmp_path / "char.png"
    ref1.write_bytes(b"char_bytes_123")
    ref2 = tmp_path / "prop.png"
    ref2.write_bytes(b"prop_bytes_456")

    def fake_run(cmd, **kwargs):
        out_file.write_bytes(b"dummy_image_data_1234567890")
        res = MagicMock()
        res.returncode = 0
        res.stdout = "{}"
        res.stderr = ""
        return res

    mock_run.side_effect = fake_run

    res = _run_flow_image_generate(
        model_alias="nano-pro",
        prompt="A cute miniature clay robot holding a gear",
        output_path=out_file,
        aspect_ratio="9:16",
        references=[ref1, ref2],
    )

    assert res == out_file
    assert mock_run.called
    first_cmd = mock_run.call_args_list[0][0][0]
    assert first_cmd[0] == "/mock/bin/gflow"
    assert "image" in first_cmd
    assert "i2i" in first_cmd  # 참조가 있으므로 i2i로 전환
    assert "--ref" in first_cmd
    assert str(ref1.resolve()) in first_cmd
    assert str(ref2.resolve()) in first_cmd


@patch("subprocess.run")
@patch("shutil.which")
def test_run_flow_video_generate(mock_which, mock_run, tmp_path):
    mock_which.return_value = "/mock/bin/gflow"
    start_img = tmp_path / "start.png"
    start_img.write_bytes(b"start_img")
    out_video = tmp_path / "out.mp4"

    def fake_run(cmd, **kwargs):
        out_video.write_bytes(b"dummy_video_data_1234567890")
        res = MagicMock()
        res.returncode = 0
        res.stdout = "{}"
        res.stderr = ""
        return res

    mock_run.side_effect = fake_run

    res = _run_flow_video_generate(
        model_alias="veo-fast",
        prompt="Smooth camera pan right",
        start_image=start_img,
        output_path=out_video,
        duration=6,
        aspect_ratio="9:16",
    )

    assert res == out_video
    assert mock_run.called
    first_cmd = mock_run.call_args_list[0][0][0]
    assert first_cmd[0] == "/mock/bin/gflow"
    assert "video" in first_cmd
    assert "i2v" in first_cmd
    assert "--model" in first_cmd
    assert "veo-fast" in first_cmd
    # 6초 지정 확인
    assert "--duration" in first_cmd
    assert "6" in first_cmd
    assert "-i" in first_cmd
    assert "Smooth camera pan right" == first_cmd[-1]


@patch("subprocess.run")
@patch("shutil.which")
def test_run_flow_video_generate_fallback_when_no_duration_control(mock_which, mock_run, tmp_path):
    mock_which.return_value = "/mock/bin/gflow"
    start_img = tmp_path / "start.png"
    start_img.write_bytes(b"start_img")
    out_video = tmp_path / "out.mp4"

    call_count = 0

    def fake_run(cmd, **kwargs):
        nonlocal call_count
        call_count += 1
        res = MagicMock()
        if call_count == 1:
            # 1차 시도: no duration control 에러 발생
            res.returncode = 1
            res.stdout = ""
            res.stderr = "the migrated Flow host renders no duration control offering '6s'"
            return res
        # 2차 시도 (--duration 없이 성공)
        out_video.write_bytes(b"dummy_video_data_1234567890")
        res.returncode = 0
        res.stdout = "{}"
        res.stderr = ""
        return res

    mock_run.side_effect = fake_run

    res = _run_flow_video_generate(
        model_alias="veo-fast",
        prompt="Smooth camera pan right",
        start_image=start_img,
        output_path=out_video,
        duration=6,
        aspect_ratio="9:16",
    )

    assert res == out_video
    assert call_count >= 2
    # 2번째 호출 커맨드에는 --duration이 제거되어 있어야 함
    second_cmd = mock_run.call_args_list[1][0][0]
    assert "--duration" not in second_cmd


@patch("time.sleep", return_value=None)
@patch("subprocess.run")
@patch("shutil.which")
def test_run_flow_video_generate_retry_on_timeout(mock_which, mock_run, mock_sleep, tmp_path):
    import subprocess
    mock_which.return_value = "/mock/bin/gflow"
    start_img = tmp_path / "start.png"
    start_img.write_bytes(b"start_img")
    out_video = tmp_path / "out.mp4"

    call_count = 0

    def fake_run(cmd, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            # 1차 시도: 5분 타임아웃 발생
            raise subprocess.TimeoutExpired(cmd=cmd, timeout=300)
        # 2차 시도: 정상 생성 성공
        out_video.write_bytes(b"dummy_video_data_1234567890")
        res = MagicMock()
        res.returncode = 0
        res.stdout = "{}"
        res.stderr = ""
        return res

    mock_run.side_effect = fake_run

    res = _run_flow_video_generate(
        model_alias="veo-fast",
        prompt="Smooth camera pan right",
        start_image=start_img,
        output_path=out_video,
        duration=6,
        aspect_ratio="9:16",
        timeout_seconds=300,
        max_retries=3,
    )

    assert res == out_video
    # gflow CLI가 1차 타임아웃 후 2차 시도까지 총 2회 호출되었는지 검증
    gflow_calls = [c for c in mock_run.call_args_list if "/mock/bin/gflow" in c[0][0][0]]
    assert len(gflow_calls) == 2


@patch("app.production.service._run_flow_image_generate")
def test_generate_scene_image_with_flow_model(mock_flow_gen, tmp_path):
    project_dir = tmp_path / "test_proj"
    project_dir.mkdir()
    video_scenes = [
        {
            "scene_id": 1,
            "narration": "첫 번째 씬",
            "start_image_prompt": "A cute character",
        }
    ]
    (project_dir / "video_scenes.json").write_text(json.dumps(video_scenes), encoding="utf-8")

    def side_effect(model_alias, prompt, output_path, aspect_ratio):
        output_path.write_bytes(b"dummy_image_data_more_than_1000_bytes_" * 50)
        return output_path

    mock_flow_gen.side_effect = side_effect

    settings = AppSettings()
    result_path = generate_scene_image_for_project(
        project_dir=project_dir,
        scene_id=1,
        settings=settings,
        model_name="flow_nano_pro",
    )

    assert result_path.exists()
    assert mock_flow_gen.called
    assert mock_flow_gen.call_args[1]["model_alias"] == "nano-pro"


@patch("app.production.service._run_flow_image_generate")
def test_generate_scene_image_with_flow_model_and_asset_sheet(mock_flow_gen, tmp_path):
    project_dir = tmp_path / "test_proj_asset"
    project_dir.mkdir()
    assets_dir = project_dir / "assets"
    assets_dir.mkdir()

    # 에셋 파일들 생성
    char_file = assets_dir / "master_character.png"
    char_file.write_bytes(b"char_bytes_123456789")
    prop1_file = assets_dir / "prop_1.png"
    prop1_file.write_bytes(b"prop1_bytes_123456789")

    video_scenes = [
        {
            "scene_id": 1,
            "narration": "석공 주인공이 망치를 들고 바닥을 점검합니다.",
            "start_image_prompt": "A craftsman holding a hammer",
            "requires_character": True,
            "required_props": ["hammer"],
        }
    ]
    (project_dir / "video_scenes.json").write_text(json.dumps(video_scenes), encoding="utf-8")

    def side_effect(model_alias, prompt, output_path, aspect_ratio, references=None):
        output_path.write_bytes(b"dummy_image_data_more_than_1000_bytes_" * 50)
        return output_path

    mock_flow_gen.side_effect = side_effect

    settings = AppSettings()
    result_path = generate_scene_image_for_project(
        project_dir=project_dir,
        scene_id=1,
        settings=settings,
        model_name="flow_nano_pro",
        use_asset_sheet=True,
    )

    assert result_path.exists()
    assert mock_flow_gen.called
    assert mock_flow_gen.call_args[1]["model_alias"] == "nano-pro"
    # references 인자로 char_file이 올바르게 전달되었는지 확인
    passed_refs = mock_flow_gen.call_args[1].get("references")
    assert passed_refs is not None
    assert char_file in passed_refs


@patch("time.sleep", return_value=None)
def test_flow_worker_profile_pool_concurrency(mock_sleep):
    count = get_flow_worker_count()
    assert count >= 1
    with _acquire_flow_profile() as p1:
        assert isinstance(p1, str) and len(p1) > 0
        if count >= 2:
            with _acquire_flow_profile() as p2:
                assert p1 != p2

