from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

from .config import ProfileError, load_profile, profile_root
from .filesystem import sha256_path
from .sync import sync

FRONTMATTER_RE = re.compile(r"\A---\n(.*?)\n---\n", re.DOTALL)
NAME_RE = re.compile(r"^name:\s*([a-z0-9-]+)\s*$", re.MULTILINE)
# Also captures indented continuation lines of folded (`>`) / literal (`|`) YAML scalars.
DESCRIPTION_RE = re.compile(r"^description:[ \t]*(.*(?:\n[ \t]+.*)*)", re.MULTILINE)
REQUIRED_FILES = ("profile.toml", "instructions/common.md", "instructions/claude.md", "instructions/codex.md")


def _frontmatter(path: Path) -> str | None:
    match = FRONTMATTER_RE.match(path.read_text(encoding="utf-8"))
    return match.group(1) if match else None


def validate_skill_dir(skills_root: Path) -> int:
    failures = 0
    if not skills_root.is_dir():
        return 0
    for skill_dir in sorted(p for p in skills_root.iterdir() if p.is_dir()):
        entry = skill_dir / "SKILL.md"
        if not entry.exists():
            print(f"ERROR missing SKILL.md: {skill_dir}")
            failures += 1
            continue
        meta = _frontmatter(entry)
        if meta is None:
            print(f"ERROR missing YAML frontmatter: {entry}")
            failures += 1
            continue
        name_match = NAME_RE.search(meta)
        desc_match = DESCRIPTION_RE.search(meta)
        if not name_match or name_match.group(1) != skill_dir.name:
            print(f"ERROR skill name must match directory: {entry}")
            failures += 1
        if not desc_match or len(desc_match.group(1).strip()) < 40:
            print(f"ERROR weak/missing description (state when to use it): {entry}")
            failures += 1
    return failures


def validate_agent_dir(agents_root: Path) -> int:
    failures = 0
    if not agents_root.is_dir():
        return 0
    for entry in sorted(agents_root.glob("*.md")):
        meta = _frontmatter(entry)
        name_match = NAME_RE.search(meta or "")
        if meta is None or not name_match or name_match.group(1) != entry.stem or not DESCRIPTION_RE.search(meta):
            print(f"ERROR agent needs frontmatter with name == file stem and description: {entry}")
            failures += 1
    return failures


def validate_profile(root: Path) -> int:
    failures = 0
    for required in REQUIRED_FILES:
        if not (root / required).exists():
            print(f"ERROR missing {root / required}")
            failures += 1
    failures += validate_skill_dir(root / "skills")
    failures += validate_agent_dir(root / "agents/claude")
    print("OK profile structure" if failures == 0 else f"{failures} profile structure error(s)")
    return failures


def warn_agent_collisions(root: Path, home: Path) -> None:
    # Global agents are opt-in; surface collisions before someone enables install_claude_agents.
    for agent in sorted((root / "agents/claude").glob("*.md")):
        live = home / ".claude/agents" / agent.name
        if (live.exists() or live.is_symlink()) and live.resolve(strict=False) != agent.resolve():
            where = os.readlink(live) if live.is_symlink() else "non-symlink file"
            print(f"WARN  user-scope agent name collision (only matters with --include-agents): {live} -> {where}")


def owner_of(path: Path, root: Path) -> str:
    target = path.resolve(strict=False)
    if target.is_relative_to(root.resolve()):
        return "agent-profile"
    if "/nanokit/" in str(target):
        return "nanokit"
    return "other"


def skill_inventory(repo: Path, root: Path, home: Path) -> int:
    """Compare a repository's project-scope skills with agent-profile and other user-scope skills."""

    def collect(base: Path) -> dict[str, Path]:
        if not base.is_dir():
            return {}
        return {p.name: p for p in base.iterdir() if (p / "SKILL.md").is_file()}

    project_skills = collect(repo / ".claude/skills")
    profile_skills = collect(root / "skills")
    user_skills = {name: path for name, path in collect(home / ".claude/skills").items() if owner_of(path, root) != "agent-profile"}
    collisions = 0
    print(f"skill inventory: project={repo}")
    for name in sorted(set(project_skills) | set(profile_skills)):
        rows = []
        hashes = {}
        for scope, table in (("project", project_skills), ("agent-profile", profile_skills), ("user", user_skills)):
            if name in table:
                label = scope if scope != "user" else f"user({owner_of(table[name], root)})"
                hashes[label] = sha256_path(table[name].resolve())
                rows.append(f"{label}={hashes[label][:10]}")
        in_project = name in project_skills
        if name in profile_skills and name in user_skills:
            verdict = "ERROR duplicate user-scope skill (agent-profile vs other owner)"
            collisions += 1
        elif in_project and len(hashes) > 1 and len(set(hashes.values())) == 1:
            verdict = "identical to user scope -> candidate for deduplication (drop the project copy)"
        elif in_project and len(hashes) > 1:
            verdict = "differs from user scope -> project specialization, or sync one side"
        elif in_project:
            verdict = "project only -> repo-specific, or candidate to import into agent-profile"
        else:
            verdict = "agent-profile only"
        print(f"  {name:28} {' '.join(rows):60} {verdict}")
    return collisions


def doctor(inventory: Path | None = None, skills_only: bool = False, root: Path | None = None, home: Path | None = None) -> int:
    root = root or profile_root()
    home = home or Path.home()
    failures = validate_profile(root)
    if inventory is not None:
        failures += skill_inventory(inventory.resolve(), root, home)
    if skills_only or inventory is not None:
        return 1 if failures else 0
    load_profile(root)
    warn_agent_collisions(root, home)
    print("--- agent-sync --check")
    if sync(root, home, check_only=True) != 0:
        failures += 1
    return 1 if failures else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Diagnose agent-profile structure, ownership and drift.")
    parser.add_argument("--skills", action="store_true", help="Validate profile structure only.")
    parser.add_argument("--inventory", type=Path, metavar="REPO", help="Compare REPO/.claude/skills with agent-profile and nanokit skills.")
    args = parser.parse_args(argv)
    try:
        return doctor(args.inventory, args.skills)
    except (ProfileError, RuntimeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
