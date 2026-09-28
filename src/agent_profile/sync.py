from __future__ import annotations

import argparse
import os
from pathlib import Path

from .config import load_profile, profile_root
from .filesystem import expand, is_same_symlink, load_json, save_json, sha256_file, sha256_tree


def state_path(home: Path, config: dict) -> Path:
    raw = config.get("state_dir", "~/.local/state/agent-profile")
    return Path(str(raw).replace("~", str(home), 1)) / "managed.json"


def ensure_symlink(source: Path, destination: Path, dry_run: bool, check_only: bool) -> tuple[str, bool]:
    if is_same_symlink(destination, source):
        return "ok", True
    if destination.exists() or destination.is_symlink():
        return "conflict", False
    if destination.parent.is_symlink():
        return "conflict-parent-symlink", False
    if check_only:
        return "missing", False
    if not dry_run:
        destination.parent.mkdir(parents=True, exist_ok=True)
        os.symlink(source, destination, target_is_directory=source.is_dir())
    return "create", True


def build_targets(root: Path, home: Path, include_agents: bool) -> list[tuple[Path, Path, str]]:
    targets: list[tuple[Path, Path, str]] = [
        (root / "instructions/common.md", home / ".claude/rules/90-agent-profile-common.md", "rule"),
        (root / "instructions/claude.md", home / ".claude/rules/91-agent-profile-claude.md", "rule"),
    ]
    for skill in sorted(p for p in (root / "skills").iterdir() if p.is_dir()):
        targets.append((skill, home / ".claude/skills" / skill.name, "skill-claude"))
        targets.append((skill, home / ".agents/skills" / skill.name, "skill-codex"))
    if include_agents:
        for agent in sorted((root / "agents/claude").glob("*.md")):
            targets.append((agent, home / ".claude/agents" / agent.name, "claude-agent"))
    return targets


def sync(root: Path, home: Path, dry_run: bool = False, check_only: bool = False, include_agents: bool = False, prune: bool = False, refresh_projects: bool = True) -> int:
    config = load_profile(root)
    state_file = state_path(home, config)
    state = load_json(state_file, {"version": 1, "paths": {}})
    conflicts = 0
    changed = 0
    for source, destination, kind in build_targets(root, home, include_agents):
        status, healthy = ensure_symlink(source, destination, dry_run, check_only)
        print(f"{status:24} {destination} -> {source}")
        if status.startswith("conflict"):
            conflicts += 1
            continue
        if status in {"create", "missing"}:
            changed += 1
        if healthy and not dry_run and not check_only:
            source_hash = sha256_tree(source) if source.is_dir() else sha256_file(source)
            state["paths"][str(destination)] = {"source": str(source), "kind": kind, "sha256": source_hash}
    if prune and not dry_run and not check_only:
        desired = {str(destination) for _, destination, _ in build_targets(root, home, include_agents)}
        for destination_text in list(state.get("paths", {})):
            if destination_text in desired:
                continue
            destination = Path(destination_text)
            source = Path(state["paths"][destination_text]["source"])
            if destination.is_symlink() and destination.resolve(strict=False) == source.resolve(strict=False):
                destination.unlink()
                print(f"prune                    {destination}")
            state["paths"].pop(destination_text, None)
    if not dry_run and not check_only:
        save_json(state_file, state)
        if refresh_projects:
            attachments = state_file.with_name("attachments.json")
            attached = load_json(attachments, {"repositories": {}})
            if attached.get("repositories"):
                from .attach import attach
                for record in attached["repositories"].values():
                    repo_root = Path(record.get("repo_root", ""))
                    if repo_root.exists():
                        print(f"refresh-attached         {repo_root}")
                        attach(repo_root, root=root, home=home)
    if conflicts:
        return 2
    if check_only and changed:
        return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Sync reusable agent profile content into user scopes.")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--check", action="store_true", help="Check drift without writing.")
    parser.add_argument("--include-agents", action="store_true", help="Also install Claude user-level subagents.")
    parser.add_argument("--prune", action="store_true", help="Remove stale paths previously owned by this profile.")
    parser.add_argument("--no-refresh-projects", action="store_true", help="Do not refresh registered project attachments.")
    parser.add_argument("--target-home", type=Path, default=Path.home())
    args = parser.parse_args(argv)
    root = profile_root()
    return sync(root, args.target_home.expanduser().resolve(), args.dry_run, args.check, args.include_agents, args.prune, not args.no_refresh_projects)


if __name__ == "__main__":
    raise SystemExit(main())
