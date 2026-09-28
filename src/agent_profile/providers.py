from __future__ import annotations

import json
from pathlib import Path

from .filesystem import merge_json

MANAGED_HEADER = "<!-- managed-by: agent-profile; generated file -->"


def read_if_exists(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8").strip()


def compose_markdown(sections: list[tuple[str, str]]) -> str:
    chunks = [MANAGED_HEADER, "", "# Generated local agent instructions"]
    for title, body in sections:
        if body.strip():
            chunks.extend(["", f"## {title}", "", body.strip()])
    return "\n".join(chunks).rstrip() + "\n"


def project_base_instructions(repo_root: Path) -> tuple[str, str]:
    agents = repo_root / "AGENTS.md"
    if agents.exists():
        return "Project AGENTS.md", agents.read_text(encoding="utf-8")
    claude = repo_root / "CLAUDE.md"
    if claude.exists():
        return "Project CLAUDE.md fallback", claude.read_text(encoding="utf-8")
    return "Project instructions", ""


def render_claude_local(project_profile: Path | None) -> str:
    if project_profile is None:
        return ""
    sections = [
        ("Private project instructions", read_if_exists(project_profile / "instructions.md")),
        ("Claude-specific private instructions", read_if_exists(project_profile / "claude.md")),
    ]
    if not any(body for _, body in sections):
        return ""
    return compose_markdown(sections)


def render_codex_override(profile_root: Path, repo_root: Path, project_profile: Path | None) -> str:
    base_title, base = project_base_instructions(repo_root)
    sections = [
        (base_title, base),
        ("Personal common instructions", read_if_exists(profile_root / "instructions/common.md")),
        ("Codex-specific personal instructions", read_if_exists(profile_root / "instructions/codex.md")),
    ]
    if project_profile is not None:
        sections.extend(
            [
                ("Private project instructions", read_if_exists(project_profile / "instructions.md")),
                ("Codex-specific private instructions", read_if_exists(project_profile / "codex.md")),
            ]
        )
    return compose_markdown(sections)


def desired_claude_settings(project_profile: Path | None) -> dict:
    if project_profile is None:
        return {}
    path = project_profile / "claude/settings.local.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def merge_claude_settings(existing: dict, desired: dict) -> dict:
    return merge_json(existing, desired)
