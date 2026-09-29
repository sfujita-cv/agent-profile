import tempfile
import unittest
from pathlib import Path

from support import make_profile, make_skill, quiet, write

from agent_profile.doctor import skill_inventory, validate_profile

ROOT = Path(__file__).resolve().parents[1]


class DoctorTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.base = Path(self._tmp.name)
        self.home = self.base / "home"
        self.profile = make_profile(self.base / "profile", skills=("shared", "cv"))

    def tearDown(self):
        self._tmp.cleanup()

    def test_repository_profile_is_valid(self):
        self.assertEqual(quiet(validate_profile, ROOT)[0], 0)

    def test_invalid_skill_name_is_reported(self):
        write(self.profile / "skills/bad/SKILL.md", "---\nname: other\ndescription: short\n---\n")
        self.assertEqual(quiet(validate_profile, self.profile)[0], 2)

    def test_folded_description_is_accepted(self):
        write(self.profile / "skills/folded/SKILL.md", "---\nname: folded\ndescription: >\n  Multi-line folded description that says\n  when to use this skill.\n---\n")
        self.assertEqual(quiet(validate_profile, self.profile)[0], 0)

    def test_skill_inventory_classifies_duplicates_and_specializations(self):
        nanokit = self.base / "nanokit/claude/skills"
        make_skill(nanokit, "plan")
        make_skill(nanokit, "shared")
        (self.home / ".claude/skills").mkdir(parents=True)
        (self.home / ".claude/skills/plan").symlink_to(nanokit / "plan")
        (self.home / ".claude/skills/shared").symlink_to(nanokit / "shared")
        repo = self.base / "repo"
        make_skill(repo / ".claude/skills", "cv")
        write(repo / ".claude/skills/plan/SKILL.md", "---\nname: plan\ndescription: project specific planning variant\n---\n")
        make_skill(repo / ".claude/skills", "repo-only")
        failures, output = quiet(skill_inventory, repo, self.profile, self.home)
        lines = {line.split()[0]: line for line in output.splitlines()[1:]}
        self.assertIn("deduplication", lines["cv"])
        self.assertIn("specialization", lines["plan"])
        self.assertIn("import into agent-profile", lines["repo-only"])
        self.assertIn("ERROR duplicate user-scope skill", lines["shared"])
        self.assertEqual(failures, 1)


if __name__ == "__main__":
    unittest.main()
