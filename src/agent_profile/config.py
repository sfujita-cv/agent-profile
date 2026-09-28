from __future__ import annotations

import tomllib
from pathlib import Path


def profile_root() -> Path:
    return Path(__file__).resolve().parents[2]


def load_profile(root: Path | None = None) -> dict:
    root = root or profile_root()
    with (root / "profile.toml").open("rb") as handle:
        return tomllib.load(handle)
