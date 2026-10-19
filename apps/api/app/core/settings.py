from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from dotenv import dotenv_values
from pydantic import BaseModel, Field, field_validator

from app.core.paths import find_repo_root


class SubtitleStyle(BaseModel):
    font_family: str = "system"
    font_weight: int = 800
    text_color: str = "#FFFFFF"
    outline_color: str = "#111111"
    position: str = "bottom-center"


class AppSettings(BaseModel):
    openai_api_key: str = ""
    youtube_api_key: str = ""
    higgsfield_api_key: str = ""
    qwen3_tts_base_url: str = "http://127.0.0.1:7860"
    reference_voice_path: str = "assets/reference_voice/reference_voice.mp3"
    reference_voice_text: str = (
        "안녕하세요 여러분. 반갑습니다. 오늘도 저희 채널을 찾아주셔서 감사합니다. "
        "영상이 도움되셨다면 구독과 좋아요를 눌러주세요."
    )
    bgm_path: str = "assets/bgm/channel_bgm.mp3"
    bgm_volume: float = 0.18
    output_dir: str = "outputs"
    default_shorts_duration_seconds: int = 45
    openai_transcription_model: str = "whisper-1"
    openai_analysis_model: str = "gpt-4.1-mini"
    yt_dlp_binary: str = "yt-dlp"
    reference_audio_filename: str = "reference_audio.wav"
    subtitle_style: SubtitleStyle = Field(default_factory=SubtitleStyle)

    @field_validator("output_dir")
    @classmethod
    def validate_output_dir(cls, value: str) -> str:
        path = Path(value)
        if path.is_absolute():
            raise ValueError("output_dir must be a relative path")
        if ".." in path.parts:
            raise ValueError("output_dir must not contain path traversal")
        return value


ENV_TO_FIELD = {
    "OPENAI_API_KEY": "openai_api_key",
    "YOUTUBE_API_KEY": "youtube_api_key",
    "HIGGSFIELD_API_KEY": "higgsfield_api_key",
    "QWEN3_TTS_BASE_URL": "qwen3_tts_base_url",
    "REFERENCE_VOICE_PATH": "reference_voice_path",
    "REFERENCE_VOICE_TEXT": "reference_voice_text",
    "BGM_PATH": "bgm_path",
    "BGM_VOLUME": "bgm_volume",
    "OUTPUT_DIR": "output_dir",
    "DEFAULT_SHORTS_DURATION_SECONDS": "default_shorts_duration_seconds",
    "OPENAI_TRANSCRIPTION_MODEL": "openai_transcription_model",
    "OPENAI_ANALYSIS_MODEL": "openai_analysis_model",
    "YT_DLP_BINARY": "yt_dlp_binary",
    "REFERENCE_AUDIO_FILENAME": "reference_audio_filename",
}


def _coerce_value(field_name: str, value: str) -> Any:
    if field_name == "bgm_volume":
        return float(value)
    if field_name == "default_shorts_duration_seconds":
        return int(value)
    return value


def _load_env_values(repo_root: Path) -> dict[str, Any]:
    raw = dict(dotenv_values(repo_root / ".env"))
    for key, value in os.environ.items():
        if key in ENV_TO_FIELD:
            raw[key] = value
    mapped: dict[str, Any] = {}
    for env_key, field_name in ENV_TO_FIELD.items():
        value = raw.get(env_key)
        if value not in (None, ""):
            mapped[field_name] = _coerce_value(field_name, str(value))
    return mapped


def _load_local_values(repo_root: Path) -> dict[str, Any]:
    path = repo_root / "config" / "local.settings.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def load_settings(repo_root: Path | None = None) -> AppSettings:
    root = repo_root or find_repo_root()
    values: dict[str, Any] = {}
    values.update(_load_env_values(root))
    values.update(_load_local_values(root))
    return AppSettings.model_validate(values)
