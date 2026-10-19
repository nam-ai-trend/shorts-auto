from pathlib import Path

import pytest

from app.references.audio import (
    AudioExtractionError,
    extract_reference_audio,
    validate_audio_upload_name,
)


def test_validate_audio_upload_name_accepts_audio_extensions():
    assert validate_audio_upload_name("voice.wav") == "reference_audio.wav"
    assert validate_audio_upload_name("voice.mp3") == "reference_audio.mp3"
    assert validate_audio_upload_name("voice.M4A") == "reference_audio.m4a"


def test_validate_audio_upload_name_rejects_non_audio():
    with pytest.raises(ValueError, match="Audio upload must be"):
        validate_audio_upload_name("notes.txt")


def test_validate_audio_upload_name_rejects_missing_extension():
    with pytest.raises(ValueError, match="Audio upload must be"):
        validate_audio_upload_name("voice")


def test_extract_reference_audio_runs_yt_dlp_command(tmp_path: Path):
    calls = []

    def fake_runner(command: list[str]):
        calls.append(command)
        output = tmp_path / "reference_audio.wav"
        output.write_bytes(b"audio")
        return 0, "", ""

    result = extract_reference_audio(
        project_dir=tmp_path,
        url="https://www.youtube.com/watch?v=abc123DEF45",
        yt_dlp_binary="yt-dlp",
        runner=fake_runner,
    )

    assert result == tmp_path / "reference_audio.wav"
    assert calls[0][0] == "yt-dlp"
    assert "--extract-audio" in calls[0]
    assert "--audio-format" in calls[0]
    assert str(tmp_path / "reference_audio.%(ext)s") in calls[0]


def test_extract_reference_audio_raises_actionable_error(tmp_path: Path):
    def fake_runner(command: list[str]):
        return 1, "", "ffmpeg not found"

    with pytest.raises(AudioExtractionError, match="ffmpeg not found"):
        extract_reference_audio(
            project_dir=tmp_path,
            url="https://www.youtube.com/watch?v=abc123DEF45",
            yt_dlp_binary="yt-dlp",
            runner=fake_runner,
        )


def test_extract_reference_audio_rejects_missing_output(tmp_path: Path):
    def fake_runner(command: list[str]):
        return 0, "ok", ""

    with pytest.raises(AudioExtractionError, match="was not created"):
        extract_reference_audio(
            project_dir=tmp_path,
            url="https://www.youtube.com/watch?v=abc123DEF45",
            yt_dlp_binary="yt-dlp",
            runner=fake_runner,
        )


def test_extract_reference_audio_wraps_missing_binary(tmp_path: Path):
    def fake_runner(command: list[str]):
        raise FileNotFoundError("missing binary")

    with pytest.raises(AudioExtractionError, match="yt-dlp binary not found"):
        extract_reference_audio(
            project_dir=tmp_path,
            url="https://www.youtube.com/watch?v=abc123DEF45",
            yt_dlp_binary="/missing/yt-dlp",
            runner=fake_runner,
        )
