from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path


@lru_cache(maxsize=1)
def project_root() -> Path:
    """Resolve repo root (contains pyproject.toml, app/, data/)."""
    if env_root := os.environ.get("BXSIMULATOR_ROOT"):
        root = Path(env_root).expanduser().resolve()
        if _looks_like_root(root):
            return root
        raise FileNotFoundError(f"BXSIMULATOR_ROOT is not a valid project root: {root}")

    here = Path(__file__).resolve()
    for candidate in (Path.cwd(), *here.parents):
        if _looks_like_root(candidate):
            return candidate.resolve()

    legacy = here.parents[2]
    if (legacy / "data" / "offline").is_dir():
        return legacy.resolve()

    raise FileNotFoundError(
        "Cannot locate BX Simulator project root. "
        "Set BXSIMULATOR_ROOT or run from the repository directory."
    )


def _looks_like_root(path: Path) -> bool:
    return (
        (path / "pyproject.toml").is_file()
        and (path / "app" / "streamlit_app.py").is_file()
        and (path / "data" / "offline").is_dir()
    )
