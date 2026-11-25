"""Two provider namespaces, their migration, and the resolution order."""
from __future__ import annotations

import os
import unittest

import _load  # noqa: F401  (loads the package)

from arkflex.ark.config import (
    AGENT_PLAN_BASE_URL,
    ARK,
    ARK_PLAN,
    ARK_STANDARD,
    CUSTOM,
    OPENAI,
    STANDARD_BASE_URL,
    ark_endpoints,
    defaults,
    first_model,
    migrate,
    openai_endpoints,
    profile_names,
    resolve,
)

OLD = {
    "profiles": {
        "standard": {"base_url": STANDARD_BASE_URL, "api_key": "std-key"},
        "agent-plan": {"base_url": AGENT_PLAN_BASE_URL + "/", "api_key": "plan-key"},
        "apiyi": {"base_url": "https://relay.invalid/v1", "api_key": "relay-key", "kind": "openai",
                  "refs_mode": "multipart", "model": "gpt-image-2.5"},
    },
    "defaults": {"image": "apiyi", "video": "standard"},
}


class MigrationTest(unittest.TestCase):
    def test_old_profiles_split_into_two_sections(self):
        migrated = migrate(OLD)
        self.assertIn("ark", migrated)
        self.assertIn("openai", migrated)
        self.assertNotIn("profiles", migrated, "the superseded section must not be kept alongside")
        self.assertEqual(migrated["ark"][ARK_STANDARD]["api_key"], "std-key")
        self.assertEqual(migrated["openai"]["apiyi"]["api_key"], "relay-key")
        self.assertEqual(migrated["openai"]["apiyi"]["refs_mode"], "multipart")
        self.assertEqual(migrated["openai"]["apiyi"]["model"], "gpt-image-2.5")

    def test_an_already_new_config_is_left_alone(self):
        new = {"ark": {"standard": {"api_key": "k"}}, "openai": {}}
        self.assertIs(migrate(new), new)


class EndpointTest(unittest.TestCase):
    def test_ark_section_has_the_two_official_surfaces(self):
        known = ark_endpoints({"ark": {"standard": {"api_key": "k"}}})
        self.assertEqual(known[ARK_STANDARD].base_url, STANDARD_BASE_URL)
        self.assertEqual(known[ARK_PLAN].base_url, AGENT_PLAN_BASE_URL)
        self.assertEqual(known[ARK_STANDARD].api_key, "k")
        self.assertTrue(known[ARK_STANDARD].is_ark)

    def test_an_extra_ark_surface_is_kept(self):
        known = ark_endpoints({"ark": {"proxy": {"base_url": "https://proxy.invalid/api/v3", "api_key": "p"}}})
        self.assertIn("proxy", known)
        self.assertEqual(known["proxy"].base_url, "https://proxy.invalid/api/v3")

    def test_openai_section_requires_a_base_url(self):
        known = openai_endpoints({"openai": {"relay": {"api_key": "k"}, "ok": {"base_url": "https://x/v1"}}})
        self.assertNotIn("relay", known, "no URL means nothing to call")
        self.assertEqual(known["ok"].provider, OPENAI)
        self.assertEqual(known["ok"].refs_mode, "json")

    def test_profile_names_offer_custom_last(self):
        names = profile_names(ARK, {"ark": {}})
        self.assertEqual(names[-1], CUSTOM)
        self.assertIn(ARK_STANDARD, names)


class ResolveTest(unittest.TestCase):
    def setUp(self):
        os.environ.pop("ARK_API_KEY", None)

    def test_ark_defaults_to_standard_and_honours_a_choice(self):
        self.assertEqual(resolve(ARK, config={}).name, ARK_STANDARD)
        chosen = resolve(ARK, profile=ARK_PLAN, config={"ark": {ARK_PLAN: {"api_key": "plan"}}})
        self.assertEqual(chosen.base_url, AGENT_PLAN_BASE_URL)
        self.assertEqual(chosen.api_key, "plan")

    def test_a_node_override_beats_the_section(self):
        chosen = resolve(
            ARK,
            profile=ARK_STANDARD,
            api_key_override="node-key",
            base_url_override="https://node.invalid/api/v3/",
            config={"ark": {ARK_STANDARD: {"api_key": "section-key"}}},
        )
        self.assertEqual(chosen.api_key, "node-key")
        self.assertEqual(chosen.base_url, "https://node.invalid/api/v3", "trailing slash trimmed")

    def test_env_is_the_ark_fallback(self):
        os.environ["ARK_API_KEY"] = "env-key"
        try:
            self.assertEqual(resolve(ARK, config={}).api_key, "env-key")
        finally:
            os.environ.pop("ARK_API_KEY", None)

    def test_an_openai_default_does_not_leak_into_the_ark_node(self):
        # defaults.image may name the relay; an Ark call must still go to Ark.
        chosen = resolve(ARK, config={"defaults": {"image": "apiyi"}, "openai": {"apiyi": {"base_url": "https://x/v1"}}})
        self.assertEqual(chosen.name, ARK_STANDARD)
        self.assertEqual(chosen.base_url, STANDARD_BASE_URL)

    def test_openai_resolves_its_section(self):
        config = {"openai": {"apiyi": {"base_url": "https://relay.invalid/v1", "api_key": "k", "refs_mode": "multipart"}}}
        self.assertEqual(resolve(OPENAI, config=config).name, "apiyi")
        self.assertEqual(resolve(OPENAI, config=config).refs_mode, "multipart")
        self.assertEqual(defaults(config)["image"], ARK_STANDARD)
        self.assertEqual(first_model(OPENAI, {"openai": {"a": {"base_url": "https://x/v1", "model": "m"}}}), "m")


if __name__ == "__main__":
    unittest.main()
