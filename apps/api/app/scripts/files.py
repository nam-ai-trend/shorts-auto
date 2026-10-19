from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from app.scripts.models import FinalScriptState, ScriptCandidate, ScriptsState


SCRIPT_CANDIDATES_FILE = "candidates.json"
SELECTED_SCRIPT_CANDIDATE_FILE = "selected_script_candidate.json"
FINAL_SCRIPT_FILE = "final_script.md"
FINAL_SCRIPT_STATE_FILE = "final_script_state.json"
SCRIPT_OUTPUT_FILES = [
    SCRIPT_CANDIDATES_FILE,
    SELECTED_SCRIPT_CANDIDATE_FILE,
    FINAL_SCRIPT_FILE,
    FINAL_SCRIPT_STATE_FILE,
]


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


def _write_json(path: Path, payload: object) -> None:
    _write_text(path, json.dumps(payload, ensure_ascii=False, indent=2))


def write_script_candidates(project_dir: Path, candidates: list[ScriptCandidate]) -> None:
    _write_json(project_dir / SCRIPT_CANDIDATES_FILE, [item.model_dump() for item in candidates])


def read_script_candidates(project_dir: Path) -> list[ScriptCandidate]:
    path = project_dir / SCRIPT_CANDIDATES_FILE
    if not path.exists():
        return []
    return [
        ScriptCandidate.model_validate(item)
        for item in json.loads(path.read_text(encoding="utf-8"))
    ]


def write_selected_script_candidate(project_dir: Path, candidate: ScriptCandidate) -> None:
    _write_json(project_dir / SELECTED_SCRIPT_CANDIDATE_FILE, candidate.model_dump())


def read_selected_script_candidate(project_dir: Path) -> ScriptCandidate | None:
    path = project_dir / SELECTED_SCRIPT_CANDIDATE_FILE
    if not path.exists():
        return None
    return ScriptCandidate.model_validate_json(path.read_text(encoding="utf-8"))


def write_final_script_state(project_dir: Path, state: FinalScriptState) -> None:
    script = state.final_script.strip() + "\n"
    # The JSON state is canonical for app reads; the markdown file is a user-facing export.
    # Write the export first and the canonical state last so interrupted writes do not expose
    # a new final script through the app without its validation metadata.
    payloads = [
        (project_dir / FINAL_SCRIPT_FILE, script),
        (
            project_dir / FINAL_SCRIPT_STATE_FILE,
            json.dumps(state.model_dump(), ensure_ascii=False, indent=2),
        ),
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


def read_final_script_state(project_dir: Path) -> FinalScriptState | None:
    path = project_dir / FINAL_SCRIPT_STATE_FILE
    if not path.exists():
        return None
    return FinalScriptState.model_validate_json(path.read_text(encoding="utf-8"))


def read_script_state(project_dir: Path) -> ScriptsState:
    final_state = read_final_script_state(project_dir)
    return ScriptsState(
        candidates=read_script_candidates(project_dir),
        selected_candidate=read_selected_script_candidate(project_dir),
        final_script=final_state.final_script if final_state else None,
        feedback=final_state.feedback if final_state else "",
        tts_validation=final_state.tts_validation if final_state else None,
    )


def clear_script_outputs(project_dir: Path) -> None:
    for filename in SCRIPT_OUTPUT_FILES:
        path = project_dir / filename
        if path.exists():
            path.unlink()
