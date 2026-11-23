"""Profiles are the point of this pack: which URL, which key, and who wins."""
from __future__ import annotations

import os
import unittest

import _load  # noqa: F401  (loads the package)

from arkflex.ark.config import (
    AGENT_PLAN_BASE_URL,
    CUSTOM,
    STANDARD_BASE_URL,
    defaults,
    profile_names,
    profiles,
    resolve,
)
from arkflex.ark.errors import explain


class ProfilesTest(unittest.TestCase):
    def test_both_official_surfaces_are_built_in(self):
        known = profiles({})
        self.assertEqual(known["standard"].base_url, STANDARD_BASE_URL)
        self.assertEqual(known["agent-plan"].base_url, AGENT_PLAN_BASE_URL)
        # Keys never ship with the package.
        self.assertEqual(known["standard"].api_key, "")
        self.assertEqual(known["agent-plan"].api_key, "")

    def test_config_overrides_a_built_in_and_adds_one(self):
        config = {
            "profiles": {
                "agent-plan": {"base_url": AGENT_PLAN_BASE_URL + "/", "api_key": "plan-key", "label": "计划"},
                "proxy": {"base_url": "https://example.invalid/api/v3", "api_key": "proxy-key"},
            }
        }
        known = profiles(config)
        self.assertEqual(known["agent-plan"].api_key, "plan-key")
        self.assertEqual(known["agent-plan"].base_url, AGENT_PLAN_BASE_URL, "a trailing slash is trimmed")
        self.assertEqual(known["agent-plan"].display, "计划")
        self.assertIn("proxy", known)
        self.assertEqual(known["proxy"].display, "proxy")

    def test_a_profile_without_a_url_is_ignored(self):
        known = profiles({"profiles": {"broken": {"api_key": "k"}, "blank": {"base_url": "  "}}})
        self.assertNotIn("broken", known)
        self.assertNotIn("blank", known)

    def test_combo_lists_every_profile_then_custom(self):
        names = profile_names({"profiles": {"proxy": {"base_url": "https://example.invalid/api/v3"}}})
        self.assertEqual(names[0], "standard")
        self.assertEqual(names[-1], CUSTOM)
        self.assertIn("proxy", names)

    def test_defaults_name_a_profile_per_kind(self):
        self.assertEqual(defaults({}), {"image": "standard", "video": "standard"})
        self.assertEqual(
            defaults({"defaults": {"image": "agent-plan", "video": "  "}}),
            {"image": "agent-plan", "video": "standard"},
        )


class ResolveTest(unittest.TestCase):
    def setUp(self):
        self._env = os.environ.pop("ARK_API_KEY", None)

    def tearDown(self):
        os.environ.pop("ARK_API_KEY", None)
        if self._env is not None:
            os.environ["ARK_API_KEY"] = self._env

    def test_the_node_profile_wins_over_the_kind_default(self):
        config = {"defaults": {"video": "standard"}}
        chosen = resolve("video", profile="agent-plan", config=config)
        self.assertEqual(chosen.base_url, AGENT_PLAN_BASE_URL)

    def test_image_and_video_can_point_at_different_surfaces(self):
        config = {
            "profiles": {
                "standard": {"base_url": STANDARD_BASE_URL, "api_key": "std"},
                "agent-plan": {"base_url": AGENT_PLAN_BASE_URL, "api_key": "plan"},
            },
            "defaults": {"image": "standard", "video": "agent-plan"},
        }
        self.assertEqual(resolve("image", config=config).base_url, STANDARD_BASE_URL)
        self.assertEqual(resolve("video", config=config).base_url, AGENT_PLAN_BASE_URL)
        self.assertEqual(resolve("video", config=config).api_key, "plan")

    def test_custom_without_a_url_falls_back_to_the_kind_default(self):
        chosen = resolve("video", profile=CUSTOM, config={"defaults": {"video": "agent-plan"}})
        self.assertEqual(chosen.base_url, AGENT_PLAN_BASE_URL)

    def test_overrides_win(self):
        config = {"profiles": {"proxy": {"base_url": "https://example.invalid/api/v3", "api_key": "x"}}}
        chosen = resolve(
            "image",
            profile="proxy",
            base_url_override="https://other.invalid/api/v3/",
            api_key_override=" y ",
            config=config,
        )
        self.assertEqual(chosen.base_url, "https://other.invalid/api/v3")
        self.assertEqual(chosen.api_key, "y")

    def test_environment_key_is_the_last_resort(self):
        os.environ["ARK_API_KEY"] = "env-key"
        self.assertEqual(resolve("image", config={}).api_key, "env-key")

    def test_a_profile_key_beats_the_environment(self):
        os.environ["ARK_API_KEY"] = "env-key"
        config = {"profiles": {"standard": {"base_url": STANDARD_BASE_URL, "api_key": "profile-key"}}}
        self.assertEqual(resolve("image", config=config).api_key, "profile-key")


class ErrorTextTest(unittest.TestCase):
    def test_a_403_names_both_surfaces(self):
        text = explain(403, {"error": {"code": "Forbidden"}}, AGENT_PLAN_BASE_URL)
        self.assertIn("Agent Plan", text)
        self.assertIn("/api/v3", text)
        self.assertIn("互不通用", text)

    def test_other_statuses_stay_short(self):
        self.assertIn("404", explain(404, "nope", STANDARD_BASE_URL))
        self.assertIn("429", explain(429, "", STANDARD_BASE_URL))
        self.assertIn("500", explain(500, "", STANDARD_BASE_URL))


if __name__ == "__main__":
    unittest.main()
