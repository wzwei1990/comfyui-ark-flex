"""The key lives inside this folder, so an uninstall is a folder delete."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import _load  # noqa: F401  (loads the package)

from arkflex.ark.store import AGENT_PLAN, STANDARD, PROFILE_URLS, key_presence, read_config, write_keys


class StoreTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.path = Path(self.dir.name) / "config.json"

    def tearDown(self):
        self.dir.cleanup()

    def test_a_missing_file_reads_empty(self):
        self.assertEqual(read_config(self.path), {})
        self.assertFalse(key_presence(self.path)["standard"])

    def test_writing_a_key_creates_its_profile_and_keeps_the_rest(self):
        self.path.write_text(json.dumps({"profiles": {"proxy": {"base_url": "https://x/api/v3"}}}), encoding="utf-8")
        presence = write_keys("std-key", None, path=self.path)
        self.assertTrue(presence["standard"])
        self.assertFalse(presence["agentPlan"])
        config = json.loads(self.path.read_text(encoding="utf-8"))
        self.assertEqual(config["profiles"][STANDARD]["api_key"], "std-key")
        self.assertEqual(config["profiles"][STANDARD]["base_url"], PROFILE_URLS[STANDARD], "the URL is filled in")
        self.assertEqual(config["profiles"]["proxy"]["base_url"], "https://x/api/v3", "other profiles survive")
        self.assertEqual(config["defaults"], {"image": STANDARD, "video": STANDARD})

    def test_both_surfaces_are_independent(self):
        write_keys("std-key", "plan-key", path=self.path)
        presence = key_presence(self.path)
        self.assertEqual(presence, {"standard": True, "agentPlan": True})
        config = json.loads(self.path.read_text(encoding="utf-8"))
        self.assertEqual(config["profiles"][AGENT_PLAN]["api_key"], "plan-key")

    def test_an_empty_string_clears_one_key_and_leaves_the_other(self):
        write_keys("std-key", "plan-key", path=self.path)
        presence = write_keys("", None, path=self.path)
        self.assertEqual(presence, {"standard": False, "agentPlan": True})
        config = json.loads(self.path.read_text(encoding="utf-8"))
        self.assertNotIn("api_key", config["profiles"][STANDARD])

    def test_whitespace_is_trimmed_and_counts_as_empty(self):
        write_keys("   ", None, path=self.path)
        self.assertFalse(key_presence(self.path)["standard"])
        write_keys("  spaced-key  ", None, path=self.path)
        config = json.loads(self.path.read_text(encoding="utf-8"))
        self.assertEqual(config["profiles"][STANDARD]["api_key"], "spaced-key")

    def test_no_temporary_files_are_left_behind(self):
        write_keys("k", None, path=self.path)
        leftovers = [name for name in self.path.parent.iterdir() if name.name.startswith(".config-")]
        self.assertEqual(leftovers, [])
        self.assertTrue(self.path.exists())


if __name__ == "__main__":
    unittest.main()
