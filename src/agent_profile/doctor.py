from __future__ import annotations

import argparse
import re
from pathlib import Path

from .attach import status as attach_status
from .config import load_profile, profile_root
from .sync import sync

NAME_RE = re.compile(r"^name:\s*([a-z0-9-]+)\s*$", re.MULTILINE)
DESCRIPTION_RE = re.compile(r"^description:\s*(.+)$", re.MULTILINE)


def validate_skills(root: Path) -> int:
    failures = 0
    seen: dict[str, Path] = {}
    for skill_dir in sorted(p for p in (root / "skills").iterdir() if p.is_dir()):
        entry = skill_dir / "SKILL.md"
        if not entry.exists():
            print(f"ERROR missing SKILL.md: {skill_dir}")
            failures += 1
            continue
        text = entry.read_text(encoding="utf-8")
        name_match = NAME_RE.search(text)
        desc_match = DESCRIPTION_RE.search(text)
        if not name_match or name_match.group(1) != skill_dir.name:
            print(f"ERROR invalid skill name: {entry}")
            failures += 1
        if not desc_match or len(desc_match.group(1).strip()) < 40:
            print(f"ERROR weak/missing description: {entry}")
            failures += 1
        name = name_match.group(1) if name_match else skill_dir.name
        if name in seen:
            print(f"ERROR duplicate skill name: {name}: {seen[name]} and {entry}")
            failures += 1
        seen[name] = entry
    if failures == 0:
        print(f"OK {len(seen)} skills")
    return failures


def doctor(project: Path | None, skills_only: bool = False) -> int:
    root = profile_root()
    failures = validate_skills(root)
    if skills_only:
        return 1 if failures else 0
    config = load_profile(root)
    for required in ("instructions/common.md", "instructions/claude.md", "instructions/codex.md", "profile.toml"):
        path = root / required
        if not path.exists():
            print(f"ERROR missing {path}")
            failures += 1
    sync_code = sync(root, Path.home(), check_only=True, include_agents=config.get("global", {}).get("install_claude_agents", False))
    if sync_code == 2:
        failures += 1
    if project is not None:
        failures += 1 if attach_status(project, root) else 0
    return 1 if failures else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Diagnose agent-profile configuration and drift.")
    parser.add_argument("--project", type=Path)
    parser.add_argument("--skills", action="store_true", help="Validate only skill structure.")
    args = parser.parse_args(argv)
    return doctor(args.project, args.skills)


if __name__ == "__main__":
    raise SystemExit(main())
