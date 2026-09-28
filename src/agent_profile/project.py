from __future__ import annotations

import re
import subprocess
import tomllib
from pathlib import Path
from urllib.parse import urlparse


def run_git(path: Path, *args: str, check: bool = True) -> str:
    proc = subprocess.run(
        ["git", "-C", str(path), *args],
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if check and proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or f"git {' '.join(args)} failed")
    return proc.stdout.strip()


def discover_repo_root(path: Path) -> Path:
    return Path(run_git(path, "rev-parse", "--show-toplevel")).resolve()


def git_common_dir(repo_root: Path) -> Path:
    raw = run_git(repo_root, "rev-parse", "--git-common-dir")
    path = Path(raw)
    if not path.is_absolute():
        path = repo_root / path
    return path.resolve()


def origin_url(repo_root: Path) -> str | None:
    value = run_git(repo_root, "remote", "get-url", "origin", check=False)
    return value or None


def normalize_remote(remote: str) -> str:
    value = remote.strip()
    scp = re.fullmatch(r"(?:[^@]+@)?([^:]+):(.+)", value)
    if scp and "://" not in value:
        host, path = scp.groups()
    else:
        parsed = urlparse(value if "://" in value else f"ssh://{value}")
        host = parsed.hostname or ""
        path = parsed.path.lstrip("/")
    if path.endswith(".git"):
        path = path[:-4]
    return f"{host.lower()}/{path.strip('/')}"


def project_slug(normalized_remote: str) -> str:
    parts = normalized_remote.split("/", 1)
    if len(parts) != 2:
        return normalized_remote.replace("/", "__")
    repo_path = parts[1]
    return repo_path.replace("/", "__")


def list_worktrees(repo_root: Path) -> list[Path]:
    output = run_git(repo_root, "worktree", "list", "--porcelain")
    paths: list[Path] = []
    for line in output.splitlines():
        if line.startswith("worktree "):
            paths.append(Path(line[9:]).resolve())
    return paths or [repo_root]


def is_tracked(repo_root: Path, relative_path: str) -> bool:
    proc = subprocess.run(
        ["git", "-C", str(repo_root), "ls-files", "--error-unmatch", "--", relative_path],
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return proc.returncode == 0


def load_toml(path: Path) -> dict:
    if not path.exists():
        return {}
    with path.open("rb") as handle:
        return tomllib.load(handle)


def find_project_profile(profile_root: Path, normalized_remote: str | None) -> Path | None:
    projects_root = profile_root / "projects"
    if normalized_remote:
        slug = project_slug(normalized_remote)
        direct = projects_root / slug
        if direct.is_dir():
            return direct
    for candidate in sorted(p for p in projects_root.iterdir() if p.is_dir() and p.name != "example"):
        config = load_toml(candidate / "project.toml")
        remotes = config.get("match", {}).get("remotes", [])
        normalized = {normalize_remote(value) for value in remotes}
        if normalized_remote and normalized_remote in normalized:
            return candidate
    return None
