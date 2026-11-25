"""Writing the two sections into the pack's own config.json."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import _load  # noqa: F401  (loads the package)

from arkflex.ark.store import presence, read_config, write_settings


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
        state = presence(self.path)
        self.assertFalse(state["ark"]["standard"])
        self.assertEqual(state["openai"]["refsMode"], "json")

    def test_ark_keys_land_in_their_own_section(self):
        state = write_settings(ark_standard="std-key", path=self.path)
        self.assertTrue(state["ark"]["standard"])
        self.assertFalse(state["ark"]["agentPlan"])
        config = self.config()
        self.assertEqual(config["ark"]["standard"]["api_key"], "std-key")
        self.assertNotIn("openai", config, "an Ark key must not create a relay entry")

    def test_openai_connection_is_one_entry(self):
        state = write_settings(
            openai_base_url="https://relay.invalid/v1",
            openai_api_key="relay-key",
            openai_refs_mode="multipart",
            openai_model="relay-model",
            path=self.path,
        )
        self.assertTrue(state["openai"]["apiKey"])
        self.assertEqual(state["openai"]["baseUrl"], "https://relay.invalid/v1")
        self.assertEqual(state["openai"]["refsMode"], "multipart")
        self.assertEqual(state["openai"]["model"], "relay-model")
        self.assertNotIn("ark", self.config())

    def test_an_empty_string_clears_only_that_value(self):
        write_settings(ark_standard="k1", ark_plan="k2", path=self.path)
        state = write_settings(ark_standard="", path=self.path)
        self.assertFalse(state["ark"]["standard"])
        self.assertTrue(state["ark"]["agentPlan"])
        self.assertNotIn("api_key", self.config()["ark"]["standard"])

    def test_whitespace_is_trimmed(self):
        write_settings(ark_standard="  spaced  ", path=self.path)
        self.assertEqual(self.config()["ark"]["standard"]["api_key"], "spaced")
        write_settings(ark_standard="   ", path=self.path)
        self.assertFalse(presence(self.path)["ark"]["standard"])

    def test_defaults_are_written_and_validated(self):
        state = write_settings(image_default="standard", path=self.path)
        self.assertEqual(state["defaults"]["image"], "standard")
        with self.assertRaises(ValueError):
            write_settings(image_default="nope", path=self.path)

    def test_an_unknown_refs_mode_is_rejected(self):
        with self.assertRaises(ValueError):
            write_settings(openai_refs_mode="base64", path=self.path)
        self.assertFalse(self.path.exists(), "a rejected write touches nothing")

    def test_writing_migrates_an_old_file(self):
        self.path.write_text(json.dumps({
            "profiles": {
                "standard": {"base_url": "https://ark.cn-beijing.volces.com/api/v3", "api_key": "old-key"},
                "apiyi": {"base_url": "https://relay.invalid/v1", "api_key": "old-relay", "kind": "openai"},
            }
        }), encoding="utf-8")
        state = write_settings(ark_plan="new-plan", path=self.path)
        self.assertTrue(state["ark"]["standard"], "the migrated key survives")
        self.assertTrue(state["openai"]["apiKey"])
        self.assertTrue(state["ark"]["agentPlan"])

    def test_model_defaults_are_written_into_the_ark_section(self):
        state = write_settings(ark_image_model="doubao-seedream-4-5", ark_video_model="doubao-seedance-2-0-260128", path=self.path)
        self.assertEqual(state["ark"]["imageModel"], "doubao-seedream-4-5")
        self.assertEqual(state["ark"]["videoModel"], "doubao-seedance-2-0-260128")
        config = self.config()
        self.assertEqual(config["ark"]["image_model"], "doubao-seedream-4-5")

    def test_model_defaults_read_back_the_shipped_values(self):
        state = presence(self.path)
        self.assertEqual(state["ark"]["imageModel"], "doubao-seedream-5-0-pro")
        self.assertEqual(state["ark"]["videoModel"], "doubao-seedance-2-5-flash-261115")
        self.assertEqual(state["openai"]["model"], "gpt-image-2.6-sunburst")

    def test_no_temporary_files_are_left_behind(self):
        write_settings(ark_standard="k", path=self.path)
        leftovers = [name for name in self.path.parent.iterdir() if name.name.startswith(".config-")]
        self.assertEqual(leftovers, [])
        self.assertTrue(self.path.exists())


if __name__ == "__main__":
    unittest.main()
