import os
import shutil
import tempfile
import unittest
from pathlib import Path

from support import make_profile, quiet

from agent_profile.sync import sync

ROOT = Path(__file__).resolve().parents[1]


class SyncTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.base = Path(self._tmp.name)
        self.home = self.base / "home"
        self.home.mkdir()
        self.profile = make_profile(self.base / "profile")

    def tearDown(self):
        self._tmp.cleanup()

    def run_sync(self, **kwargs):
        return quiet(sync, kwargs.pop("root", self.profile), self.home, **kwargs)

    def test_real_profile_first_sync_and_idempotence(self):
        code, _ = quiet(sync, ROOT, self.home)
        self.assertEqual(code, 0)
        self.assertTrue((self.home / ".claude/rules/90-agent-profile-common.md").is_symlink())
        self.assertTrue((self.home / ".agents/skills/python-cv-implementation").is_symlink())
        code, _ = quiet(sync, ROOT, self.home, check_only=True)
        self.assertEqual(code, 0)

    def test_first_sync_creates_links_and_stable_path(self):
        self.assertEqual(self.run_sync()[0], 0)
        self.assertEqual((self.home / ".config/agent-profile/current").resolve(), self.profile.resolve())
        self.assertEqual((self.home / ".claude/skills/demo-skill").resolve(), (self.profile / "skills/demo-skill").resolve())
        self.assertTrue((self.home / ".local/state/agent-profile/managed.json").exists())
        code, output = self.run_sync()
        self.assertEqual(code, 0)
        self.assertNotIn("create", output)

    def test_check_reports_drift_without_writing(self):
        self.assertEqual(self.run_sync(check_only=True)[0], 2)
        self.assertFalse((self.home / ".claude").exists())

    def test_foreign_file_is_not_overwritten(self):
        foreign = self.home / ".claude/rules/90-agent-profile-common.md"
        foreign.parent.mkdir(parents=True)
        foreign.write_text("foreign\n", encoding="utf-8")
        code, output = self.run_sync()
        self.assertEqual(code, 2)
        self.assertIn("conflict", output)
        self.assertEqual(foreign.read_text(encoding="utf-8"), "foreign\n")
        # Safe items are still processed after a conflict.
        self.assertTrue((self.home / ".claude/skills/demo-skill").is_symlink())

    def test_nanokit_skill_collision_is_reported(self):
        nanokit_skill = self.base / "nanokit/claude/skills/demo-skill"
        nanokit_skill.mkdir(parents=True)
        live = self.home / ".claude/skills/demo-skill"
        live.parent.mkdir(parents=True)
        live.symlink_to(nanokit_skill)
        code, output = self.run_sync()
        self.assertEqual(code, 2)
        self.assertIn(str(nanokit_skill), output)
        self.assertEqual(os.readlink(live), str(nanokit_skill))

    def test_symlinked_parent_directory_is_never_written_through(self):
        other = self.base / "other-tool/skills"
        other.mkdir(parents=True)
        (self.home / ".claude").mkdir()
        (self.home / ".claude/skills").symlink_to(other)
        code, output = self.run_sync()
        self.assertEqual(code, 2)
        self.assertIn("conflict-parent-symlink", output)
        self.assertEqual(list(other.iterdir()), [])

    def test_removed_skill_is_stale_until_prune(self):
        self.run_sync()
        shutil.rmtree(self.profile / "skills/demo-skill")
        link = self.home / ".claude/skills/demo-skill"
        code, output = self.run_sync()
        self.assertEqual(code, 0)
        self.assertIn("stale", output)
        self.assertTrue(link.is_symlink())
        self.assertEqual(self.run_sync(check_only=True)[0], 2)
        self.assertEqual(self.run_sync(prune=True)[0], 0)
        self.assertFalse(link.is_symlink())
        self.assertEqual(self.run_sync(check_only=True)[0], 0)

    def test_prune_never_removes_foreign_replacement(self):
        self.run_sync()
        shutil.rmtree(self.profile / "skills/demo-skill")
        link = self.home / ".claude/skills/demo-skill"
        link.unlink()
        link.mkdir()
        self.assertEqual(self.run_sync(prune=True)[0], 0)
        self.assertTrue(link.is_dir())

    def test_moved_profile_repairs_broken_symlinks(self):
        self.run_sync()
        moved = self.base / "moved-profile"
        shutil.move(self.profile, moved)
        link = self.home / ".claude/skills/demo-skill"
        self.assertFalse(link.exists())
        code, output = self.run_sync(root=moved)
        self.assertEqual(code, 0)
        self.assertIn("relink", output)
        self.assertEqual(link.resolve(), (moved / "skills/demo-skill").resolve())

    def test_global_flags_are_honoured(self):
        profile = make_profile(self.base / "flags", global_options="install_skills = false\ninstall_claude_rules = false\n")
        self.assertEqual(self.run_sync(root=profile)[0], 0)
        self.assertFalse((self.home / ".claude/skills").exists())
        self.assertFalse((self.home / ".claude/rules").exists())

    def test_agents_only_with_opt_in(self):
        (self.profile / "agents/claude/debugger.md").write_text("---\nname: debugger\ndescription: x\n---\n", encoding="utf-8")
        self.run_sync()
        self.assertFalse((self.home / ".claude/agents/debugger.md").exists())
        self.run_sync(include_agents=True)
        self.assertTrue((self.home / ".claude/agents/debugger.md").is_symlink())


if __name__ == "__main__":
    unittest.main()
