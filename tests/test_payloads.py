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


class VideoDerivationTest(unittest.TestCase):
    """Ark wants ratio + tier + seconds; a shot table gives pixels + frames."""

    def test_ratio_comes_from_the_pixels(self):
        self.assertEqual(video_module.ratio_for(1344, 768), "16:9")
        self.assertEqual(video_module.ratio_for(768, 1344), "9:16")
        self.assertEqual(video_module.ratio_for(1024, 1024), "1:1")
        self.assertEqual(video_module.ratio_for(0, 0, "9:16"), "9:16", "no pixels, keep the widget")

    def test_resolution_tier_comes_from_the_long_side(self):
        self.assertEqual(video_module.resolution_for(1920, 1080), "1080p")
        self.assertEqual(video_module.resolution_for(1344, 768), "720p")
        self.assertEqual(video_module.resolution_for(832, 480), "480p")
        self.assertEqual(video_module.resolution_for(0, 0, "1080p"), "1080p")

    def test_duration_accepts_frames_or_seconds_and_clamps_to_ark(self):
        self.assertEqual(video_module.duration_for(124, 5, 24), 5)
        self.assertEqual(video_module.duration_for(0, 7, 24), 7)
        self.assertEqual(video_module.duration_for(0, 1, 24), 4, "Ark's floor")
        self.assertEqual(video_module.duration_for(900, 5, 24), 30, "Ark's ceiling")


class MultipartTest(unittest.TestCase):
    def test_fields_and_files_are_framed_for_images_edits(self):
        from arkflex.ark.client import build_multipart

        body = build_multipart(
            {"model": "m", "prompt": "p", "n": "1"},
            [("ref0.png", b"PNGDATA", "image/png")],
            "BOUND",
        )
        text = body.decode("utf-8", "replace")
        self.assertIn('Content-Disposition: form-data; name="model"', text)
        self.assertIn('name="image[]"; filename="ref0.png"', text)
        self.assertIn("Content-Type: image/png", text)
        self.assertIn("PNGDATA", text)
        self.assertTrue(body.endswith(b"--BOUND--\r\n"), "the closing boundary ends the body")


class PayloadTest(unittest.TestCase):
    def setUp(self):
        self._video_encoder = video_module.tensor_to_data_url
        self._common_encoder = common.tensor_to_data_url
        video_module.tensor_to_data_url = _fake_data_url
        # image.py imports this lazily from common, so stub it at the source.
        common.tensor_to_data_url = _fake_data_url

    def tearDown(self):
        video_module.tensor_to_data_url = self._video_encoder
        common.tensor_to_data_url = self._common_encoder

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

    def test_explicit_width_height_win_and_are_validated_per_dialect(self):
        # Both zero: the preset.
        self.assertEqual(image_module.resolve_size("1280x720 (16:9)", 0, 0), "1280x720")
        # Both given: the caller's own frame.
        self.assertEqual(image_module.resolve_size("1024x1024 (1:1)", 1344, 768), "1344x768")
        # Ark insists on multiples of 16; an OpenAI endpoint does not.
        with self.assertRaises(ArkError):
            image_module.resolve_size("1024x1024 (1:1)", 1000, 768, kind="ark")
        self.assertEqual(image_module.resolve_size("1024x1024 (1:1)", 1000, 768, kind="openai"), "1000x768")
        # Half a pair is a mistake, not a preset.
        with self.assertRaises(ArkError):
            image_module.resolve_size("1024x1024 (1:1)", 1024, 0)

    def test_image_payload_carries_seed_only_when_given(self):
        body = image_module.payload_for(model="m", prompt="p", size="1024x1024", watermark=False, seed=-1)
        self.assertNotIn("seed", body)
        body = image_module.payload_for(model="m", prompt="p", size="1024x1024", watermark=False, seed=7)
        self.assertEqual(body["seed"], 7)

    def test_watermark_is_omitted_for_openai_endpoints(self):
        body = image_module.payload_for(model="m", prompt="p", size="1024x1024", watermark=None, seed=-1)
        self.assertNotIn("watermark", body, "an OpenAI endpoint may reject unknown fields")
        body = image_module.payload_for(model="m", prompt="p", size="1024x1024", watermark=False, seed=-1)
        self.assertIn("watermark", body)

    def test_ark_only_fields_never_reach_a_relay(self):
        ark = image_module.payload_for(model="m", prompt="p", size="1024x1024", watermark=False, seed=-1)
        self.assertEqual(ark["response_format"], "url")
        relay = image_module.payload_for(
            model="m", prompt="p", size="1024x1024", watermark=None, seed=-1, provider="openai"
        )
        self.assertNotIn("response_format", relay)
        self.assertNotIn("watermark", relay)
        self.assertEqual(relay["size"], "1024x1024")

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
