import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from agent_profile.project import normalize_remote, project_slug


class ProjectTests(unittest.TestCase):
    def test_normalize_github_https_and_ssh(self):
        expected = "github.com/acme/vision-engine"
        self.assertEqual(normalize_remote("https://github.com/acme/vision-engine.git"), expected)
        self.assertEqual(normalize_remote("git@github.com:acme/vision-engine.git"), expected)
        self.assertEqual(normalize_remote("ssh://git@github.com/acme/vision-engine.git"), expected)

    def test_project_slug_excludes_host(self):
        self.assertEqual(project_slug("github.com/acme/vision-engine"), "acme__vision-engine")


if __name__ == "__main__":
    unittest.main()
