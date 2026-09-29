from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_tree(path: Path, ignore: frozenset[str] = frozenset()) -> str:
    digest = hashlib.sha256()
    for item in sorted(p for p in path.rglob("*") if p.is_file() and p.name not in ignore):
        digest.update(item.relative_to(path).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(item.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def sha256_path(path: Path, ignore: frozenset[str] = frozenset()) -> str:
    return sha256_tree(path, ignore) if path.is_dir() else sha256_file(path)


def atomic_write_text(path: Path, content: str) -> None:
    # Write to a sibling temp file and rename so readers (Claude/Codex) never see a partial file.
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.tmp-{os.getpid()}")
    tmp.write_text(content, encoding="utf-8")
    os.replace(tmp, path)


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, value: Any) -> None:
    atomic_write_text(path, json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def is_same_symlink(destination: Path, source: Path) -> bool:
    if not destination.is_symlink():
        return False
    return destination.resolve(strict=False) == source.resolve(strict=False)


def has_symlink_parent(path: Path, stop: Path) -> bool:
    """Return True if any ancestor of ``path`` below ``stop`` is a symlink.

    A symlinked parent such as ``~/.claude/skills -> ~/nanokit/...`` means writing
    into it would modify another tool's repository.
    """
    for parent in path.parents:
        if parent == stop:
            return False
        if parent.is_symlink():
            return True
    return False
