import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from agent_profile.attach import attach, detach, status


def git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)


def make_profile(root: Path) -> None:
    (root / "instructions").mkdir(parents=True)
    (root / "projects/example").mkdir(parents=True)
    (root / "instructions/common.md").write_text("COMMON\n", encoding="utf-8")
    (root / "instructions/codex.md").write_text("CODEX\n", encoding="utf-8")
    (root / "profile.toml").write_text('version = 1\nstate_dir = "~/.local/state/agent-profile"\n', encoding="utf-8")


class AttachTests(unittest.TestCase):
    def test_codex_override_preserves_project_instructions(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            profile = base / "profile"
            home = base / "home"
            repo = base / "repo"
            make_profile(profile)
            repo.mkdir()
            git(repo, "init")
            git(repo, "config", "user.email", "test@example.com")
            git(repo, "config", "user.name", "Test")
            (repo / "AGENTS.md").write_text("PROJECT\n", encoding="utf-8")
            git(repo, "add", "AGENTS.md")
            git(repo, "commit", "-m", "init")
            git(repo, "remote", "add", "origin", "git@github.com:example/repo.git")

            self.assertEqual(attach(repo, root=profile, home=home), 0)
            content = (repo / "AGENTS.override.md").read_text(encoding="utf-8")
            self.assertIn("PROJECT", content)
            self.assertIn("COMMON", content)
            self.assertIn("CODEX", content)
            self.assertEqual(status(repo, root=profile), 0)
            exclude = Path(subprocess.run(["git", "-C", str(repo), "rev-parse", "--git-common-dir"], check=True, text=True, stdout=subprocess.PIPE).stdout.strip())
            if not exclude.is_absolute():
                exclude = repo / exclude
            exclude_text = (exclude / "info/exclude").read_text(encoding="utf-8")
            self.assertIn("AGENTS.override.md", exclude_text)
            self.assertEqual(detach(repo, root=profile, home=home), 0)
            self.assertFalse((repo / "AGENTS.override.md").exists())

    def test_project_profile_generates_private_overlay_and_merges_settings(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            profile = base / "profile"
            home = base / "home"
            repo = base / "repo"
            make_profile(profile)
            project = profile / "projects/example__repo"
            (project / "claude").mkdir(parents=True)
            (project / "skills/private-check").mkdir(parents=True)
            (project / "instructions.md").write_text("PRIVATE\n", encoding="utf-8")
            (project / "claude.md").write_text("CLAUDE-PRIVATE\n", encoding="utf-8")
            (project / "project.toml").write_text('[match]\nremotes = ["github.com/example/repo"]\n', encoding="utf-8")
            (project / "claude/settings.local.json").write_text('{"env":{"A":"1"}}\n', encoding="utf-8")
            (project / "skills/private-check/SKILL.md").write_text('---\nname: private-check\ndescription: Private project check used for testing.\n---\n\n# Check\n', encoding="utf-8")

            repo.mkdir()
            git(repo, "init")
            git(repo, "config", "user.email", "test@example.com")
            git(repo, "config", "user.name", "Test")
            (repo / "CLAUDE.md").write_text("TEAM\n", encoding="utf-8")
            git(repo, "add", "CLAUDE.md")
            git(repo, "commit", "-m", "init")
            git(repo, "remote", "add", "origin", "https://github.com/example/repo.git")
            (repo / ".claude").mkdir()
            (repo / ".claude/settings.local.json").write_text('{"permissions":{"allow":["Bash(git *)"]}}\n', encoding="utf-8")

            self.assertEqual(attach(repo, root=profile, home=home), 0)
            self.assertIn("PRIVATE", (repo / "CLAUDE.local.md").read_text(encoding="utf-8"))
            settings = json.loads((repo / ".claude/settings.local.json").read_text(encoding="utf-8"))
            self.assertEqual(settings["env"]["A"], "1")
            self.assertEqual(settings["permissions"]["allow"], ["Bash(git *)"])
            self.assertTrue((repo / ".claude/skills/private-check/SKILL.md").exists())
            self.assertTrue((repo / ".agents/skills/private-check/SKILL.md").exists())

    def test_tracked_override_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            profile = base / "profile"
            home = base / "home"
            repo = base / "repo"
            make_profile(profile)
            repo.mkdir()
            git(repo, "init")
            git(repo, "config", "user.email", "test@example.com")
            git(repo, "config", "user.name", "Test")
            (repo / "AGENTS.override.md").write_text("TRACKED\n", encoding="utf-8")
            git(repo, "add", "AGENTS.override.md")
            git(repo, "commit", "-m", "init")
            self.assertEqual(attach(repo, root=profile, home=home), 2)
            self.assertEqual((repo / "AGENTS.override.md").read_text(encoding="utf-8"), "TRACKED\n")


if __name__ == "__main__":
    unittest.main()
