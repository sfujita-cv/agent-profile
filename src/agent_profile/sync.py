from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from .config import STABLE_PATH, ProfileError, global_option, load_profile, profile_root, state_dir
from .filesystem import has_symlink_parent, is_same_symlink, load_json, save_json, sha256_path

DRIFT_STATUSES = {"create", "relink"}


def state_path(home: Path, config: dict) -> Path:
    return state_dir(home, config) / "managed.json"


def build_targets(root: Path, home: Path, config: dict, include_agents: bool) -> list[tuple[Path, Path, str]]:
    targets: list[tuple[Path, Path, str]] = [(root, home / STABLE_PATH, "stable-path")]
    if global_option(config, "install_claude_rules", True):
        targets += [
            (root / "instructions/common.md", home / ".claude/rules/90-agent-profile-common.md", "rule"),
            (root / "instructions/claude.md", home / ".claude/rules/91-agent-profile-claude.md", "rule"),
        ]
    if global_option(config, "install_skills", True):
        for skill in sorted(p for p in (root / "skills").iterdir() if (p / "SKILL.md").is_file()):
            targets.append((skill, home / ".claude/skills" / skill.name, "skill-claude"))
            targets.append((skill, home / ".agents/skills" / skill.name, "skill-codex"))
    if include_agents:
        for agent in sorted((root / "agents/claude").glob("*.md")):
            targets.append((agent, home / ".claude/agents" / agent.name, "claude-agent"))
    return targets


def plan_link(source: Path, destination: Path, home: Path, managed: dict) -> str:
    if is_same_symlink(destination, source):
        return "ok"
    if has_symlink_parent(destination, home):
        return "conflict-parent-symlink"
    if destination.is_symlink():
        # Relink only symlinks this profile created earlier (e.g. the repository was moved),
        # proven by the recorded link text. Anything else belongs to nanokit or the user.
        record = managed.get(str(destination))
        if record and os.readlink(destination) == record.get("source"):
            return "relink"
        return "conflict"
    if destination.exists():
        return "conflict"
    return "create"


def apply_link(source: Path, destination: Path, action: str) -> None:
    if action == "relink":
        destination.unlink()
    destination.parent.mkdir(parents=True, exist_ok=True)
    os.symlink(source, destination, target_is_directory=source.is_dir())


def describe_conflict(destination: Path) -> str:
    if destination.is_symlink():
        return f"existing: {os.readlink(destination)}"
    if destination.exists():
        return "existing: non-symlink path"
    return "existing: parent directory is a symlink owned by another tool"



def sync(
    root: Path,
    home: Path,
    dry_run: bool = False,
    check_only: bool = False,
    include_agents: bool | None = None,
    prune: bool = False,
) -> int:
    """Link profile content into user scope. Exit 0 = ok, 2 = conflict or drift (check mode)."""
    config = load_profile(root)
    if include_agents is None:
        include_agents = global_option(config, "install_claude_agents", False)
    write = not dry_run and not check_only
    state_file = state_path(home, config)
    state = load_json(state_file, {"version": 1, "paths": {}})
    managed: dict = state.setdefault("paths", {})
    conflicts = 0
    drift = 0
    targets = build_targets(root, home, config, include_agents)
    for source, destination, kind in targets:
        action = plan_link(source, destination, home, managed)
        print(f"{action:26} {destination} -> {source}")
        if action.startswith("conflict"):
            print(f"{'':26} {describe_conflict(destination)}")
            conflicts += 1
            continue
        if action in DRIFT_STATUSES:
            drift += 1
            if write:
                apply_link(source, destination, action)
        if write:
            record = {"source": str(source), "kind": kind}
            if kind != "stable-path":
                record["sha256"] = sha256_path(source)
            managed[str(destination)] = record
    desired = {str(destination) for _, destination, _ in targets}
    for destination_text in sorted(set(managed) - desired):
        destination = Path(destination_text)
        recorded = managed[destination_text].get("source")
        ours = destination.is_symlink() and os.readlink(destination) == recorded
        if not ours:
            # Already gone or replaced by someone else: forget it, never touch it.
            if write:
                managed.pop(destination_text)
            continue
        if prune and write:
            destination.unlink()
            managed.pop(destination_text)
            print(f"{'prune':26} {destination}")
        else:
            print(f"{'stale (use --prune)':26} {destination} -> {recorded}")
            drift += 1
    if write:
        save_json(state_file, state)
    if conflicts:
        return 2
    if check_only and drift:
        return 2
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Sync reusable agent profile content into user scopes.")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--check", action="store_true", help="Report drift without writing (exit 2 on drift/conflict).")
    parser.add_argument("--include-agents", action="store_true", default=None, help="Also install Claude user-level subagents (overrides profile.toml).")
    parser.add_argument("--prune", action="store_true", help="Remove stale symlinks previously created by this profile.")
    parser.add_argument("--target-home", type=Path, default=Path.home())
    args = parser.parse_args(argv)
    try:
        return sync(
            profile_root(),
            args.target_home.expanduser().resolve(),
            dry_run=args.dry_run,
            check_only=args.check,
            include_agents=args.include_agents,
            prune=args.prune,
        )
    except (ProfileError, RuntimeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
