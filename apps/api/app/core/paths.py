from __future__ import annotations

from pathlib import Path


def find_repo_root(start: Path | None = None) -> Path:
    current = (start or Path(__file__)).resolve()
    for candidate in [current, *current.parents]:
        # 모노레포 루트 식별을 위해 package.json과 pnpm-workspace.yaml(또는 apps 디렉터리)을 확인
        if (candidate / "package.json").exists() and (
            (candidate / "pnpm-workspace.yaml").exists() or (candidate / "apps").exists()
        ):
            return candidate
    raise RuntimeError("Could not find repository root")
