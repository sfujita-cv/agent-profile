import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from agent_profile.sync import sync


ROOT = Path(__file__).resolve().parents[1]


class SyncTests(unittest.TestCase):
    def test_first_sync_and_idempotence(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            self.assertEqual(sync(ROOT, home, refresh_projects=False), 0)
            common = home / ".claude/rules/90-agent-profile-common.md"
            skill = home / ".agents/skills/python-cv-implementation"
            self.assertTrue(common.is_symlink())
            self.assertTrue(skill.is_symlink())
            self.assertEqual(sync(ROOT, home, refresh_projects=False), 0)

    def test_foreign_destination_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            foreign = home / ".claude/rules/90-agent-profile-common.md"
            foreign.parent.mkdir(parents=True)
            foreign.write_text("foreign\n", encoding="utf-8")
            self.assertEqual(sync(ROOT, home, refresh_projects=False), 2)
            self.assertEqual(foreign.read_text(encoding="utf-8"), "foreign\n")


if __name__ == "__main__":
    unittest.main()
