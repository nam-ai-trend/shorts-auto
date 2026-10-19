from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Callable


ALLOWED_AUDIO_EXTENSIONS = {".wav", ".mp3", ".m4a", ".aac", ".webm"}
MAX_AUDIO_UPLOAD_BYTES = 200 * 1024 * 1024
UPLOAD_CHUNK_SIZE = 1024 * 1024


class AudioExtractionError(RuntimeError):
    pass


def validate_audio_upload_name(filename: str) -> str:
    suffix = Path(filename).suffix.lower()
    if suffix not in ALLOWED_AUDIO_EXTENSIONS:
        raise ValueError("Audio upload must be wav, mp3, m4a, aac, or webm")
    return f"reference_audio{suffix}"


def default_runner(command: list[str]) -> tuple[int, str, str]:
    completed = subprocess.run(command, capture_output=True, text=True, check=False)
    return completed.returncode, completed.stdout, completed.stderr


async def save_uploaded_audio(
    file: Any,
    output_path: Path,
    max_bytes: int = MAX_AUDIO_UPLOAD_BYTES,
) -> Path:
    temp_path = None
    total_bytes = 0
    try:
        with tempfile.NamedTemporaryFile(
            "wb",
            dir=output_path.parent,
            prefix=f".{output_path.name}.",
            suffix=".tmp",
            delete=False,
        ) as temp_file:
            temp_path = Path(temp_file.name)
            while True:
                chunk = await file.read(UPLOAD_CHUNK_SIZE)
                if not chunk:
                    break
                total_bytes += len(chunk)
                if total_bytes > max_bytes:
                    raise ValueError("Audio upload is too large")
                temp_file.write(chunk)
            temp_file.flush()
            os.fsync(temp_file.fileno())
        if total_bytes == 0:
            raise ValueError("Audio upload must not be empty")
        temp_path.replace(output_path)
        return output_path
    finally:
        if temp_path is not None and temp_path.exists():
            temp_path.unlink()


def extract_reference_audio(
    project_dir: Path,
    url: str,
    yt_dlp_binary: str,
    runner: Callable[[list[str]], tuple[int, str, str]] = default_runner,
) -> Path:
    output_template = str(project_dir / "reference_audio.%(ext)s")
    command = [
        yt_dlp_binary,
        "--extract-audio",
        "--audio-format",
        "wav",
        "--output",
        output_template,
        url,
    ]
    try:
        returncode, stdout, stderr = runner(command)
    except FileNotFoundError as exc:
        raise AudioExtractionError(f"yt-dlp binary not found: {yt_dlp_binary}") from exc
    if returncode != 0:
        message = stderr.strip() or stdout.strip() or "yt-dlp failed"
        raise AudioExtractionError(message)
    output_path = project_dir / "reference_audio.wav"
    if not output_path.exists():
        raise AudioExtractionError("yt-dlp completed but reference_audio.wav was not created")
    return output_path
