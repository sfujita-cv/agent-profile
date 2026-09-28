from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any


def expand(path: str | Path) -> Path:
    return Path(path).expanduser().resolve(strict=False)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_tree(path: Path) -> str:
    digest = hashlib.sha256()
    for item in sorted(p for p in path.rglob("*") if p.is_file()):
        digest.update(item.relative_to(path).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(item.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def atomic_write_text(path: Path, content: str) -> None:
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
    current = path.parent
    stop = stop.resolve(strict=False)
    while True:
        if current.is_symlink():
            return True
        if current == stop or current.parent == current:
            return False
        current = current.parent


def merge_json(existing: Any, desired: Any) -> Any:
    if isinstance(existing, dict) and isinstance(desired, dict):
        merged = dict(existing)
        for key, value in desired.items():
            merged[key] = merge_json(merged[key], value) if key in merged else value
        return merged
    if isinstance(existing, list) and isinstance(desired, list):
        merged = list(existing)
        for value in desired:
            if value not in merged:
                merged.append(value)
        return merged
    return desired
