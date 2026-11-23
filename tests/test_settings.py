"""Keys typed in ComfyUI's Settings dialog, and how they rank against the rest."""
from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path

import _load  # noqa: F401  (loads the package)

from arkflex.ark import settings as settings_module
from arkflex.ark.config import AGENT_PLAN_BASE_URL, STANDARD_BASE_URL, resolve
from arkflex.ark.settings import PLAN_KEY_ID, STANDARD_KEY_ID, key_for_profile, read_settings


class SettingsFileTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.path = Path(self.dir.name) / "comfy.settings.json"
        self._original = settings_module.user_settings_path
        settings_module.user_settings_path = lambda: self.path

    def tearDown(self):
        settings_module.user_settings_path = self._original
        self.dir.cleanup()

    def write(self, value):
        self.path.write_text(json.dumps(value), encoding="utf-8")

    def test_a_missing_or_broken_file_reads_as_empty(self):
        self.assertEqual(read_settings(), {})
        self.path.write_text("{not json", encoding="utf-8")
        self.assertEqual(read_settings(), {})
        self.path.write_text("[1,2]", encoding="utf-8")
        self.assertEqual(read_settings(), {})

    def test_each_surface_reads_its_own_key(self):
        self.write({STANDARD_KEY_ID: "std-key", PLAN_KEY_ID: "plan-key"})
        self.assertEqual(key_for_profile("standard", STANDARD_BASE_URL), "std-key")
        self.assertEqual(key_for_profile("agent-plan", AGENT_PLAN_BASE_URL), "plan-key")

    def test_a_plan_url_implies_the_plan_key(self):
        self.write({STANDARD_KEY_ID: "std-key", PLAN_KEY_ID: "plan-key"})
        self.assertEqual(key_for_profile("custom", AGENT_PLAN_BASE_URL), "plan-key")
        self.assertEqual(key_for_profile("custom", STANDARD_BASE_URL), "std-key")

    def test_blank_or_non_string_values_are_ignored(self):
        self.write({STANDARD_KEY_ID: "   ", PLAN_KEY_ID: 42})
        self.assertEqual(key_for_profile("standard", STANDARD_BASE_URL), "")
        self.assertEqual(key_for_profile("agent-plan", AGENT_PLAN_BASE_URL), "")

    # ── precedence ───────────────────────────────────────────────────────

    def test_settings_beat_the_environment_but_lose_to_a_profile(self):
        self.write({STANDARD_KEY_ID: "from-settings"})
        os.environ.pop("ARK_API_KEY", None)
        self.assertEqual(resolve("image", config={}).api_key, "from-settings")

        os.environ["ARK_API_KEY"] = "from-env"
        try:
            self.assertEqual(resolve("image", config={}).api_key, "from-settings", "settings win over env")
        finally:
            os.environ.pop("ARK_API_KEY", None)

        config = {"profiles": {"standard": {"base_url": STANDARD_BASE_URL, "api_key": "from-profile"}}}
        self.assertEqual(resolve("image", config=config).api_key, "from-profile", "a profile key wins")

    def test_a_node_override_beats_everything(self):
        self.write({STANDARD_KEY_ID: "from-settings"})
        chosen = resolve("image", api_key_override="from-node", config={})
        self.assertEqual(chosen.api_key, "from-node")


if __name__ == "__main__":
    unittest.main()
