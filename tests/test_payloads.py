"""Request bodies, size parsing and the small helpers around them.

Nothing here touches the network, and the tensor encoder is stubbed: torch is a
ComfyUI runtime dependency, not a test dependency.
"""
from __future__ import annotations

import unittest

import _load  # noqa: F401  (loads the package)

from arkflex.ark.errors import ArkError, task_failure
from arkflex.nodes import common
from arkflex.nodes import image as image_module
from arkflex.nodes import video as video_module


def _fake_data_url(image):
    """Enough to prove the content array carries a data URL."""
    return f"data:image/png;base64,STUB-{getattr(image, 'name', 'x')}"


class TensorStub:
    name = "img"


class PayloadTest(unittest.TestCase):
    def setUp(self):
        self._video_encoder = video_module.tensor_to_data_url
        self._image_encoder = image_module.tensor_to_data_url
        video_module.tensor_to_data_url = _fake_data_url
        image_module.tensor_to_data_url = _fake_data_url

    def tearDown(self):
        video_module.tensor_to_data_url = self._video_encoder
        image_module.tensor_to_data_url = self._image_encoder

    # ── video content ────────────────────────────────────────────────────

    def test_text_mode_sends_only_the_prompt(self):
        content = video_module.build_content(prompt="a cat", mode="文生视频 / text")
        self.assertEqual(content, [{"type": "text", "text": "a cat"}])

    def test_first_frame_mode_adds_one_conditioning_image(self):
        content = video_module.build_content(prompt="p", mode="首帧 / first_frame", first_frame=TensorStub())
        self.assertEqual(len(content), 2)
        self.assertEqual(content[1]["role"], "first_frame")
        self.assertTrue(content[1]["image_url"]["url"].startswith("data:image/png;base64,"))

    def test_first_and_last_mode_needs_both(self):
        content = video_module.build_content(
            prompt="p", mode="首尾帧 / first_and_last", first_frame=TensorStub(), last_frame=TensorStub()
        )
        self.assertEqual([part.get("role") for part in content], [None, "first_frame", "last_frame"])
        with self.assertRaises(ArkError):
            video_module.build_content(prompt="p", mode="首尾帧 / first_and_last", first_frame=TensorStub())

    def test_reference_mode_sends_every_reference_and_refuses_an_empty_set(self):
        content = video_module.build_content(
            prompt="p", mode="参考图 / reference", refs=[TensorStub(), None, TensorStub()]
        )
        self.assertEqual([part.get("role") for part in content], [None, "reference_image", "reference_image"])
        with self.assertRaises(ArkError):
            video_module.build_content(prompt="p", mode="参考图 / reference", refs=[None])

    def test_a_missing_image_in_first_frame_mode_is_explained(self):
        with self.assertRaises(ArkError) as caught:
            video_module.build_content(prompt="p", mode="首帧 / first_frame")
        self.assertIn("first_frame", str(caught.exception))

    # ── image payload ────────────────────────────────────────────────────

    def test_size_labels_become_pixels(self):
        self.assertEqual(image_module.size_value("1280x720 (16:9)"), "1280x720")
        self.assertEqual(image_module.size_value("1600x1600 (1:1)"), "1600x1600")
        with self.assertRaises(ArkError):
            image_module.size_value("huge")

    def test_image_payload_carries_seed_only_when_given(self):
        body = image_module.payload_for(model="m", prompt="p", size="1024x1024", watermark=False, seed=-1)
        self.assertNotIn("seed", body)
        body = image_module.payload_for(model="m", prompt="p", size="1024x1024", watermark=False, seed=7)
        self.assertEqual(body["seed"], 7)

    def test_image_payload_includes_references_as_data_urls(self):
        body = image_module.payload_for(
            model="m", prompt="p", size="1024x1024", watermark=True, seed=-1, refs=[TensorStub(), None]
        )
        self.assertEqual(len(body["image"]), 1)
        self.assertTrue(body["image"][0].startswith("data:image/png;base64,"))

    # ── shared helpers ───────────────────────────────────────────────────

    def test_extra_json_is_a_shallow_merge(self):
        payload = {"a": 1, "b": 2}
        merged = common.merge_extra(payload, '{"b": 3, "c": 4}')
        self.assertEqual(merged, {"a": 1, "b": 3, "c": 4})
        self.assertIs(merged, payload, "the original dict is updated in place")
        self.assertEqual(common.merge_extra({"a": 1}, "   "), {"a": 1})

    def test_extra_json_must_be_an_object(self):
        with self.assertRaises(ArkError):
            common.merge_extra({}, "{not json}")
        with self.assertRaises(ArkError):
            common.merge_extra({}, "[1, 2]")

    def test_custom_model_beats_the_dropdown(self):
        self.assertEqual(common.model_id("doubao-x", "ep-123"), "ep-123")
        self.assertEqual(common.model_id("doubao-x", "  "), "doubao-x")
        with self.assertRaises(ArkError):
            common.model_id("", "")

    def test_output_names_are_sanitised(self):
        self.assertEqual(common.safe_stem("a b/c..d"), "abc..d")
        self.assertEqual(common.safe_stem("///"), "ark")
        self.assertEqual(common.video_ext("https://x/y.mp4?sig=1", "mov"), ".mp4")
        self.assertEqual(common.video_ext("https://x/y", "mov"), ".mov")
        self.assertEqual(common.video_ext("https://x/y", "mp4"), ".mp4")


class TaskFailureTest(unittest.TestCase):
    def test_structured_error_wins(self):
        text = task_failure({"status": "failed", "error": {"code": "InvalidParameter", "message": "bad prompt"}})
        self.assertIn("InvalidParameter", text)
        self.assertIn("bad prompt", text)

    def test_string_error_is_used_verbatim(self):
        self.assertIn("boom", task_failure({"status": "failed", "error": "boom"}))

    def test_a_bare_status_still_says_something(self):
        text = task_failure({"status": "failed"})
        self.assertIn("failed", text)


if __name__ == "__main__":
    unittest.main()
