from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from app.references.models import ReferenceCandidate, ReferenceState
from app.scripts.files import clear_script_outputs


CANDIDATES_FILE = "reference_candidates.json"
SELECTED_REFERENCE_FILE = "selected_reference.json"
REFERENCE_SCRIPT_FILE = "reference_script.md"
REFERENCE_RAW_STT_FILE = "reference_raw_stt.json"
REFERENCE_ANALYSIS_FILE = "reference_analysis.json"
REFERENCE_ANALYSIS_MARKDOWN_FILE = "reference_analysis.md"
REFERENCE_AUDIO_FILE = "reference_audio.wav"
REFERENCE_AUDIO_PREFIX = "reference_audio"
DERIVED_REFERENCE_FILES = [
    REFERENCE_RAW_STT_FILE,
    REFERENCE_SCRIPT_FILE,
    REFERENCE_ANALYSIS_FILE,
    REFERENCE_ANALYSIS_MARKDOWN_FILE,
]
ANALYSIS_REFERENCE_FILES = [
    REFERENCE_ANALYSIS_FILE,
    REFERENCE_ANALYSIS_MARKDOWN_FILE,
]
DOWNSTREAM_REFERENCE_FILES = [
    REFERENCE_AUDIO_FILE,
    *DERIVED_REFERENCE_FILES,
]


def _write_json(path: Path, payload: object) -> None:
    _write_text(path, json.dumps(payload, ensure_ascii=False, indent=2))


def _write_text(path: Path, payload: str) -> None:
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as temp_file:
            temp_path = Path(temp_file.name)
            temp_file.write(payload)
            temp_file.flush()
            os.fsync(temp_file.fileno())
        os.replace(temp_path, path)
    finally:
        if temp_path is not None and temp_path.exists():
            temp_path.unlink()


def write_reference_candidates(project_dir: Path, candidates: list[ReferenceCandidate]) -> None:
    _write_json(project_dir / CANDIDATES_FILE, [candidate.model_dump() for candidate in candidates])


def read_reference_candidates(project_dir: Path) -> list[ReferenceCandidate]:
    path = project_dir / CANDIDATES_FILE
    if not path.exists():
        return []
    return [
        ReferenceCandidate.model_validate(item)
        for item in json.loads(path.read_text(encoding="utf-8"))
    ]


def write_selected_reference(project_dir: Path, candidate: ReferenceCandidate) -> None:
    _write_json(project_dir / SELECTED_REFERENCE_FILE, candidate.model_dump())


def read_selected_reference(project_dir: Path) -> ReferenceCandidate | None:
    path = project_dir / SELECTED_REFERENCE_FILE
    if not path.exists():
        return None
    return ReferenceCandidate.model_validate_json(path.read_text(encoding="utf-8"))


def write_reference_script(project_dir: Path, script: str) -> None:
    _write_text(project_dir / REFERENCE_SCRIPT_FILE, script)


def write_reference_raw_stt(project_dir: Path, raw_stt: dict) -> None:
    _write_json(project_dir / REFERENCE_RAW_STT_FILE, raw_stt)


def write_reference_analysis_files(project_dir: Path, analysis: dict, markdown: str) -> None:
    payloads = [
        (project_dir / REFERENCE_ANALYSIS_FILE, json.dumps(analysis, ensure_ascii=False, indent=2)),
        (project_dir / REFERENCE_ANALYSIS_MARKDOWN_FILE, markdown),
    ]
    temp_paths: list[tuple[Path, Path]] = []
    try:
        for target_path, payload in payloads:
            with tempfile.NamedTemporaryFile(
                "w",
                encoding="utf-8",
                dir=project_dir,
                prefix=f".{target_path.name}.",
                suffix=".tmp",
                delete=False,
            ) as temp_file:
                temp_path = Path(temp_file.name)
                temp_file.write(payload)
                temp_file.flush()
                os.fsync(temp_file.fileno())
            temp_paths.append((temp_path, target_path))
        for temp_path, target_path in temp_paths:
            os.replace(temp_path, target_path)
    finally:
        for temp_path, _ in temp_paths:
            if temp_path.exists():
                temp_path.unlink()


def read_reference_script(project_dir: Path) -> str | None:
    path = project_dir / REFERENCE_SCRIPT_FILE
    if not path.exists():
        return None
    return path.read_text(encoding="utf-8")


def clear_downstream_reference_outputs(project_dir: Path) -> None:
    clear_reference_audio_files(project_dir, keep_name="")
    for filename in DOWNSTREAM_REFERENCE_FILES:
        path = project_dir / filename
        if path.exists():
            path.unlink()
    clear_script_outputs(project_dir)


def clear_derived_reference_outputs(project_dir: Path) -> None:
    for filename in DERIVED_REFERENCE_FILES:
        path = project_dir / filename
        if path.exists():
            path.unlink()
    clear_script_outputs(project_dir)


def clear_reference_analysis_outputs(project_dir: Path) -> None:
    for filename in ANALYSIS_REFERENCE_FILES:
        path = project_dir / filename
        if path.exists():
            path.unlink()
    clear_script_outputs(project_dir)


def clear_reference_audio_files(project_dir: Path, keep_name: str) -> None:
    for path in project_dir.glob(f"{REFERENCE_AUDIO_PREFIX}.*"):
        if path.name != keep_name and path.is_file():
            path.unlink()


def read_reference_state(project_dir: Path) -> ReferenceState:
    analysis_path = project_dir / REFERENCE_ANALYSIS_FILE
    analysis_md_path = project_dir / REFERENCE_ANALYSIS_MARKDOWN_FILE
    analysis = json.loads(analysis_path.read_text(encoding="utf-8")) if analysis_path.exists() else None
    analysis_markdown = analysis_md_path.read_text(encoding="utf-8") if analysis_md_path.exists() else None
    return ReferenceState(
        candidates=read_reference_candidates(project_dir),
        selected_reference=read_selected_reference(project_dir),
        reference_script=read_reference_script(project_dir),
        analysis=analysis,
        analysis_markdown=analysis_markdown,
    )
