import contextlib
import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

SKILL_TEMPLATE = "---\nname: {name}\ndescription: Test skill {name} used by the agent-profile test-suite only.\n---\n\n# {name}\n"


def write(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def make_skill(base: Path, name: str) -> Path:
    write(base / name / "SKILL.md", SKILL_TEMPLATE.format(name=name))
    return base / name


def make_profile(root: Path, skills: tuple[str, ...] = ("demo-skill",), global_options: str = "") -> Path:
    write(root / "profile.toml", f'version = 1\nstate_dir = "~/.local/state/agent-profile"\n\n[global]\n{global_options}')
    write(root / "instructions/common.md", "COMMON\n")
    write(root / "instructions/claude.md", "CLAUDE\n")
    write(root / "instructions/codex.md", "CODEX\n")
    (root / "agents/claude").mkdir(parents=True)
    for name in skills:
        make_skill(root / "skills", name)
    return root


def quiet(func, *args, **kwargs):
    """Call func with stdout captured; return (result, captured_text)."""
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        result = func(*args, **kwargs)
    return result, buffer.getvalue()

