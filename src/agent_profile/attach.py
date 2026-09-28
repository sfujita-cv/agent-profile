from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

from .config import load_profile, profile_root
from .filesystem import atomic_write_text, load_json, save_json, sha256_file, sha256_tree
from .project import (
    discover_repo_root,
    find_project_profile,
    git_common_dir,
    is_tracked,
    list_worktrees,
    normalize_remote,
    origin_url,
)
from .providers import MANAGED_HEADER, desired_claude_settings, merge_claude_settings, render_claude_local, render_codex_override

BEGIN = "# BEGIN agent-profile managed excludes"
END = "# END agent-profile managed excludes"
EXCLUDES = [
    "CLAUDE.local.md",
    "AGENTS.override.md",
    ".claude/settings.local.json",
]


def attachments_path(home: Path, config: dict) -> Path:
    raw = config.get("state_dir", "~/.local/state/agent-profile")
    return Path(str(raw).replace("~", str(home), 1)) / "attachments.json"


def update_exclude(repo_root: Path, add: bool, dry_run: bool, extra_paths: list[str] | None = None) -> None:
    exclude = git_common_dir(repo_root) / "info/exclude"
    current = exclude.read_text(encoding="utf-8") if exclude.exists() else ""
    lines = current.splitlines()
    cleaned: list[str] = []
    inside = False
    for line in lines:
        if line == BEGIN:
            inside = True
            continue
        if line == END:
            inside = False
            continue
        if not inside:
            cleaned.append(line)
    if add:
        if cleaned and cleaned[-1] != "":
            cleaned.append("")
        cleaned.extend([BEGIN, *EXCLUDES, *(extra_paths or []), END])
    content = "\n".join(cleaned).rstrip() + "\n" if cleaned else ""
    if not dry_run:
        exclude.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(exclude, content)


def can_replace_generated(path: Path) -> bool:
    if not path.exists():
        return True
    if path.suffix == ".md":
        return path.read_text(encoding="utf-8", errors="replace").startswith(MANAGED_HEADER)
    return False


def write_generated(repo_root: Path, relative: str, content: str, dry_run: bool) -> tuple[bool, str]:
    destination = repo_root / relative
    if is_tracked(repo_root, relative):
        return False, f"tracked:{relative}"
    if destination.exists() and not can_replace_generated(destination):
        return False, f"foreign:{relative}"
    if not dry_run:
        atomic_write_text(destination, content)
    return True, f"write:{relative}"


def merge_settings(repo_root: Path, desired: dict, dry_run: bool) -> tuple[bool, str]:
    if not desired:
        return True, "skip:.claude/settings.local.json"
    relative = ".claude/settings.local.json"
    if is_tracked(repo_root, relative):
        return False, f"tracked:{relative}"
    destination = repo_root / relative
    existing = {}
    if destination.exists():
        try:
            existing = json.loads(destination.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return False, f"invalid-json:{relative}"
    merged = merge_claude_settings(existing, desired)
    if not dry_run:
        destination.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(destination, json.dumps(merged, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    return True, f"merge:{relative}"


def _managed_marker(destination: Path) -> Path:
    if destination.is_dir():
        return destination / ".agent-profile-managed"
    return destination.with_name(destination.name + ".agent-profile-managed")


def _copy_managed(source: Path, destination: Path, worktree: Path, dry_run: bool) -> str:
    rel = destination.relative_to(worktree).as_posix()
    if is_tracked(worktree, rel):
        return f"tracked:{rel}"
    marker = _managed_marker(destination)
    if destination.exists() and not marker.exists():
        return f"foreign:{rel}"
    if not dry_run:
        if destination.exists():
            if destination.is_dir():
                shutil.rmtree(destination)
            else:
                destination.unlink()
            if marker.exists() and marker.is_file():
                marker.unlink()
        destination.parent.mkdir(parents=True, exist_ok=True)
        if source.is_dir():
            shutil.copytree(source, destination)
            (destination / ".agent-profile-managed").write_text("managed\n", encoding="utf-8")
        else:
            shutil.copy2(source, destination)
            marker.write_text("managed\n", encoding="utf-8")
    return f"copy:{rel}"


def project_extension_paths(project_profile: Path | None) -> list[str]:
    if project_profile is None:
        return []
    paths: list[str] = []
    skills = project_profile / "skills"
    if skills.exists():
        for source in sorted(p for p in skills.iterdir() if p.name != ".gitkeep"):
            paths.extend([f".claude/skills/{source.name}", f".agents/skills/{source.name}"])
    agents = project_profile / "agents"
    if agents.exists():
        for source in sorted(p for p in agents.iterdir() if p.name != ".gitkeep"):
            paths.append(f".claude/agents/{source.name}")
            if source.is_file():
                paths.append(f".claude/agents/{source.name}.agent-profile-managed")
    return paths


def copy_project_extensions(worktree: Path, project_profile: Path | None, dry_run: bool) -> list[str]:
    if project_profile is None:
        return []
    messages: list[str] = []
    skills = project_profile / "skills"
    if skills.exists():
        for source in sorted(p for p in skills.iterdir() if p.name != ".gitkeep"):
            messages.append(_copy_managed(source, worktree / ".claude/skills" / source.name, worktree, dry_run))
            messages.append(_copy_managed(source, worktree / ".agents/skills" / source.name, worktree, dry_run))
    agents = project_profile / "agents"
    if agents.exists():
        for source in sorted(p for p in agents.iterdir() if p.name != ".gitkeep"):
            messages.append(_copy_managed(source, worktree / ".claude/agents" / source.name, worktree, dry_run))
    return messages


def attach_one(profile_root_path: Path, worktree: Path, project_profile: Path | None, dry_run: bool) -> tuple[int, list[str], dict]:
    messages: list[str] = []
    conflicts = 0
    claude_local = render_claude_local(project_profile)
    if claude_local:
        ok, message = write_generated(worktree, "CLAUDE.local.md", claude_local, dry_run)
        conflicts += 0 if ok else 1
        messages.append(message)
    codex = render_codex_override(profile_root_path, worktree, project_profile)
    ok, message = write_generated(worktree, "AGENTS.override.md", codex, dry_run)
    conflicts += 0 if ok else 1
    messages.append(message)
    desired = desired_claude_settings(project_profile)
    ok, message = merge_settings(worktree, desired, dry_run)
    conflicts += 0 if ok else 1
    messages.append(message)
    ext_messages = copy_project_extensions(worktree, project_profile, dry_run)
    conflicts += sum(1 for value in ext_messages if value.startswith(("tracked:", "foreign:")))
    messages.extend(ext_messages)
    record = {
        "generated": [m.split(":", 1)[1] for m in messages if m.startswith("write:")],
        "messages": messages,
    }
    return conflicts, messages, record


def attach(path: Path, root: Path | None = None, home: Path | None = None, dry_run: bool = False) -> int:
    root = root or profile_root()
    home = home or Path.home()
    config = load_profile(root)
    repo_root = discover_repo_root(path)
    remote = origin_url(repo_root)
    normalized = normalize_remote(remote) if remote else None
    project_profile = find_project_profile(root, normalized)
    worktrees = list_worktrees(repo_root)
    conflicts = 0
    records: dict[str, dict] = {}
    update_exclude(repo_root, True, dry_run, project_extension_paths(project_profile))
    for worktree in worktrees:
        count, messages, record = attach_one(root, worktree, project_profile, dry_run)
        conflicts += count
        records[str(worktree)] = record
        for message in messages:
            print(f"{worktree}: {message}")
    if not dry_run:
        state_file = attachments_path(home, config)
        state = load_json(state_file, {"version": 1, "repositories": {}})
        key = normalized or str(repo_root)
        state["repositories"][key] = {
            "repo_root": str(repo_root),
            "remote": remote,
            "profile": str(project_profile) if project_profile else None,
            "worktrees": records,
        }
        save_json(state_file, state)
    return 2 if conflicts else 0


def status(path: Path, root: Path | None = None) -> int:
    root = root or profile_root()
    repo_root = discover_repo_root(path)
    remote = origin_url(repo_root)
    project_profile = find_project_profile(root, normalize_remote(remote) if remote else None)
    drift = 0
    for worktree in list_worktrees(repo_root):
        expected_codex = render_codex_override(root, worktree, project_profile)
        codex = worktree / "AGENTS.override.md"
        if not codex.exists() or codex.read_text(encoding="utf-8") != expected_codex:
            print(f"drift {codex}")
            drift += 1
        expected_claude = render_claude_local(project_profile)
        claude = worktree / "CLAUDE.local.md"
        if expected_claude and (not claude.exists() or claude.read_text(encoding="utf-8") != expected_claude):
            print(f"drift {claude}")
            drift += 1
    return 1 if drift else 0


def detach(path: Path, root: Path | None = None, home: Path | None = None, dry_run: bool = False) -> int:
    root = root or profile_root()
    home = home or Path.home()
    config = load_profile(root)
    repo_root = discover_repo_root(path)
    for worktree in list_worktrees(repo_root):
        for relative in ("CLAUDE.local.md", "AGENTS.override.md"):
            target = worktree / relative
            if target.exists() and can_replace_generated(target):
                print(f"remove {target}")
                if not dry_run:
                    target.unlink()
        for root_rel in (".claude/skills", ".agents/skills"):
            extension_root = worktree / root_rel
            if extension_root.exists():
                for marker in extension_root.glob("*/.agent-profile-managed"):
                    target = marker.parent
                    print(f"remove {target}")
                    if not dry_run:
                        shutil.rmtree(target)
        agents_root = worktree / ".claude/agents"
        if agents_root.exists():
            for marker in agents_root.glob("*.agent-profile-managed"):
                target = marker.with_name(marker.name.removesuffix(".agent-profile-managed"))
                print(f"remove {target}")
                if not dry_run:
                    if target.exists():
                        target.unlink()
                    marker.unlink()
    update_exclude(repo_root, False, dry_run)
    if not dry_run:
        state_file = attachments_path(home, config)
        state = load_json(state_file, {"version": 1, "repositories": {}})
        remote = origin_url(repo_root)
        key = normalize_remote(remote) if remote else str(repo_root)
        state.get("repositories", {}).pop(key, None)
        save_json(state_file, state)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Attach private/local agent overlays to a Git repository.")
    parser.add_argument("path", nargs="?", type=Path, default=Path.cwd())
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--status", action="store_true")
    group.add_argument("--refresh", action="store_true")
    group.add_argument("--detach", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    if args.status:
        return status(args.path)
    if args.detach:
        return detach(args.path, dry_run=args.dry_run)
    return attach(args.path, dry_run=args.dry_run)


if __name__ == "__main__":
    raise SystemExit(main())
