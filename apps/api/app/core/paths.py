from __future__ import annotations

from pathlib import Path


def find_repo_root(start: Path | None = None) -> Path:
    current = (start or Path(__file__)).resolve()
    for candidate in [current, *current.parents]:
        if (candidate / "package.json").exists() and (candidate / "docs").exists():
            return candidate
    raise RuntimeError("Could not find repository root")
