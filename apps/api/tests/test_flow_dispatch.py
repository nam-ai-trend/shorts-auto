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


@patch("time.sleep", return_value=None)
def test_flow_worker_profile_pool_concurrency(mock_sleep):
    count = get_flow_worker_count()
    assert count >= 1
    with _acquire_flow_profile() as p1:
        assert isinstance(p1, str) and len(p1) > 0
        if count >= 2:
            with _acquire_flow_profile() as p2:
                assert p1 != p2

