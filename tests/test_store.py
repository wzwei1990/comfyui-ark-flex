"""The key lives inside this folder, so an uninstall is a folder delete."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import _load  # noqa: F401  (loads the package)

from arkflex.ark.store import (
    AGENT_PLAN,
    STANDARD,
    PROFILE_URLS,
    key_presence,
    read_config,
    read_defaults,
    write_keys,
)


class StoreTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.path = Path(self.dir.name) / "config.json"

    def tearDown(self):
        self.dir.cleanup()

    def config(self):
        return json.loads(self.path.read_text(encoding="utf-8"))

    def test_a_missing_file_reads_empty(self):
        self.assertEqual(read_config(self.path), {})
        self.assertFalse(key_presence(self.path)["standard"])
        self.assertEqual(read_defaults(self.path), {"image": STANDARD, "video": STANDARD}, "defaults have a fallback")

    def test_writing_a_key_creates_its_profile_and_keeps_the_rest(self):
        self.path.write_text(json.dumps({"profiles": {"proxy": {"base_url": "https://x/api/v3"}}}), encoding="utf-8")
        saved = write_keys("std-key", None, path=self.path)
        self.assertTrue(saved["keys"]["standard"])
        self.assertFalse(saved["keys"]["agentPlan"])
        config = self.config()
        self.assertEqual(config["profiles"][STANDARD]["api_key"], "std-key")
        self.assertEqual(config["profiles"][STANDARD]["base_url"], PROFILE_URLS[STANDARD], "the URL is filled in")
        self.assertEqual(config["profiles"]["proxy"]["base_url"], "https://x/api/v3", "other profiles survive")
        self.assertEqual(config["defaults"], {"image": STANDARD, "video": STANDARD})

    def test_both_surfaces_are_independent(self):
        write_keys("std-key", "plan-key", path=self.path)
        self.assertEqual(key_presence(self.path), {"standard": True, "agentPlan": True})
        self.assertEqual(self.config()["profiles"][AGENT_PLAN]["api_key"], "plan-key")

    def test_an_empty_string_clears_one_key_and_leaves_the_other(self):
        write_keys("std-key", "plan-key", path=self.path)
        saved = write_keys("", None, path=self.path)
        self.assertEqual(saved["keys"], {"standard": False, "agentPlan": True})
        self.assertNotIn("api_key", self.config()["profiles"][STANDARD])

    def test_whitespace_is_trimmed_and_counts_as_empty(self):
        write_keys("   ", None, path=self.path)
        self.assertFalse(key_presence(self.path)["standard"])
        write_keys("  spaced-key  ", None, path=self.path)
        self.assertEqual(self.config()["profiles"][STANDARD]["api_key"], "spaced-key")

    # ── defaults ─────────────────────────────────────────────────────────

    def test_defaults_are_written_and_preserved(self):
        saved = write_keys(image_default=AGENT_PLAN, path=self.path)
        self.assertEqual(saved["defaults"], {"image": AGENT_PLAN, "video": STANDARD})
        self.assertEqual(read_defaults(self.path), {"image": AGENT_PLAN, "video": STANDARD})

        # A later key write must not reset the defaults.
        write_keys("std-key", None, path=self.path)
        self.assertEqual(read_defaults(self.path), {"image": AGENT_PLAN, "video": STANDARD})

    def test_an_unknown_default_is_rejected(self):
        with self.assertRaises(ValueError):
            write_keys(video_default="agentplan", path=self.path)
        self.assertFalse(self.path.exists(), "a rejected write touches nothing")

    def test_no_temporary_files_are_left_behind(self):
        write_keys("k", None, path=self.path)
        leftovers = [name for name in self.path.parent.iterdir() if name.name.startswith(".config-")]
        self.assertEqual(leftovers, [])
        self.assertTrue(self.path.exists())


if __name__ == "__main__":
    unittest.main()
