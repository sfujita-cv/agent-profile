from __future__ import annotations

import tomllib
from pathlib import Path

DEFAULT_STATE_DIR = "~/.local/state/agent-profile"
# Stable path that external tools (e.g. a future nanokit overlay provider) can reference
# regardless of where this repository is cloned.
STABLE_PATH = ".config/agent-profile/current"


class ProfileError(RuntimeError):
    """Fatal configuration error (exit code 1)."""


def profile_root() -> Path:
    return Path(__file__).resolve().parents[2]


def load_profile(root: Path | None = None) -> dict:
    root = root or profile_root()
    path = root / "profile.toml"
    if not path.exists():
        raise ProfileError(f"missing {path}")
    try:
        with path.open("rb") as handle:
            return tomllib.load(handle)
    except tomllib.TOMLDecodeError as exc:
        raise ProfileError(f"invalid {path}: {exc}") from exc


def expand_home(raw: str, home: Path) -> Path:
    # Expand against the target home instead of Path.expanduser() so --target-home and tests work.
    if raw == "~":
        return home
    if raw.startswith("~/"):
        return home / raw[2:]
    return Path(raw)


def state_dir(home: Path, config: dict) -> Path:
    return expand_home(str(config.get("state_dir", DEFAULT_STATE_DIR)), home)


def global_option(config: dict, key: str, default: bool) -> bool:
    return bool(config.get("global", {}).get(key, default))
