"""Video generation on Volcengine Ark (Seedance family)."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..ark.errors import ArkError
from .common import (
    COMMON_OPTIONS,
    PROFILE_INPUTS,
    client_for,
    merge_extra,
    model_id,
    output_dir,
    safe_stem,
    tensor_to_data_url,
    video_ext,
)

try:  # ComfyUI >= 0.3 exposes the VIDEO type; older hosts get a path only.
    from comfy_api.latest import VideoFromFile

    HAS_VIDEO_TYPE = True
except Exception:  # pragma: no cover - depends on the host
    HAS_VIDEO_TYPE = False

VIDEO_MODELS = [
    "doubao-seedance-2-5-flash-261115",
    "doubao-seedance-2-5-260628",
    "doubao-seedance-2-0-260128",
    "doubao-seedance-2-0-fast-260128",
    "doubao-seedance-2-0-mini",
    "doubao-seedance-1-5-pro-251215",
    "doubao-seedance-1-0-pro-250528",
]

MODES = ["文生视频 / text", "首帧 / first_frame", "首尾帧 / first_and_last", "参考图 / reference"]
RESOLUTIONS = ["480p", "720p", "1080p"]
RATIOS = ["16:9", "9:16", "1:1", "4:3", "3:4", "21:9", "adaptive"]


def build_content(
    *,
    prompt: str,
    mode: str,
    first_frame: Any = None,
    last_frame: Any = None,
    refs: list[Any] | None = None,
) -> list[dict[str, Any]]:
    """The `content` array Ark expects, for the chosen conditioning mode."""
    content: list[dict[str, Any]] = [{"type": "text", "text": prompt}]

    def image_part(image: Any, role: str) -> dict[str, Any]:
        return {
            "type": "image_url",
            "image_url": {"url": tensor_to_data_url(image)},
            "role": role,
        }

    if mode.startswith("首帧"):
        if first_frame is None:
            raise ArkError("首帧模式需要接一张 first_frame 图片。")
        content.append(image_part(first_frame, "first_frame"))
    elif mode.startswith("首尾帧"):
        if first_frame is None or last_frame is None:
            raise ArkError("首尾帧模式需要同时接 first_frame 与 last_frame。")
        content.append(image_part(first_frame, "first_frame"))
        content.append(image_part(last_frame, "last_frame"))
    elif mode.startswith("参考图"):
        usable = [image for image in (refs or []) if image is not None]
        if not usable:
            raise ArkError("参考图模式至少需要接一张 ref_imageN。")
        for image in usable:
            content.append(image_part(image, "reference_image"))
    return content


class ArkVideo:
    """One async Seedance task, downloaded and returned as a VIDEO."""

    CATEGORY = "Ark / 火山方舟"
    FUNCTION = "generate"
    RETURN_NAMES = ("video", "path") if HAS_VIDEO_TYPE else ("path",)
    RETURN_TYPES = ("VIDEO", "STRING") if HAS_VIDEO_TYPE else ("STRING",)

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, Any]:
        return {
            "required": {
                "profile": PROFILE_INPUTS["profile"],
                "prompt": ("STRING", {"default": "", "multiline": True}),
                "model": (VIDEO_MODELS, {"default": VIDEO_MODELS[0]}),
                "mode": (MODES, {"default": MODES[0]}),
                "resolution": (RESOLUTIONS, {"default": "720p"}),
                "ratio": (RATIOS, {"default": "16:9"}),
                "duration": ("INT", {"default": 5, "min": 4, "max": 30}),
                "generate_audio": ("BOOLEAN", {"default": True}),
                "output_format": (["mp4", "mov"], {"default": "mp4"}),
                "base_url_override": PROFILE_INPUTS["base_url_override"],
                "api_key_override": PROFILE_INPUTS["api_key_override"],
                "seed": COMMON_OPTIONS["seed"],
                "watermark": COMMON_OPTIONS["watermark"],
                "timeout": COMMON_OPTIONS["timeout"],
                "poll_seconds": COMMON_OPTIONS["poll_seconds"],
                "extra_json": COMMON_OPTIONS["extra_json"],
            },
            "optional": {
                "custom_model": ("STRING", {"default": "", "tooltip": "填了就用它（端点 id 或新模型名）。"}),
                "first_frame": ("IMAGE",),
                "last_frame": ("IMAGE",),
                "ref_image1": ("IMAGE",),
                "ref_image2": ("IMAGE",),
                "ref_image3": ("IMAGE",),
            },
        }

    def generate(
        self,
        profile: str,
        prompt: str,
        model: str,
        mode: str,
        resolution: str,
        ratio: str,
        duration: int,
        generate_audio: bool,
        output_format: str,
        base_url_override: str,
        api_key_override: str,
        seed: int,
        watermark: bool,
        timeout: int,
        poll_seconds: int,
        extra_json: str,
        custom_model: str = "",
        first_frame: Any = None,
        last_frame: Any = None,
        ref_image1: Any = None,
        ref_image2: Any = None,
        ref_image3: Any = None,
    ):
        client, chosen = client_for(
            "video",
            profile=profile,
            base_url_override=base_url_override,
            api_key_override=api_key_override,
        )
        payload: dict[str, Any] = {
            "model": model_id(model, custom_model),
            "content": build_content(
                prompt=prompt,
                mode=mode,
                first_frame=first_frame,
                last_frame=last_frame,
                refs=[ref_image1, ref_image2, ref_image3],
            ),
            "resolution": resolution,
            "ratio": ratio,
            "duration": int(duration),
            "generate_audio": bool(generate_audio),
            "watermark": bool(watermark),
        }
        if int(seed) >= 0:
            payload["seed"] = int(seed)
        payload = merge_extra(payload, extra_json)

        task_id = client.submit_video(payload)
        task = client.wait_video(task_id, poll_seconds=float(poll_seconds), timeout=float(timeout))
        content = task.get("content") or {}
        video_url = content.get("video_url") if isinstance(content, dict) else None
        if not isinstance(video_url, str) or not video_url:
            raise ArkError(f"任务成功但没有 video_url：{json.dumps(task, ensure_ascii=False)[:400]}")

        ext = video_ext(video_url, output_format)
        path = client.download(
            video_url,
            output_dir("video"),
            filename=f"{safe_stem(prompt, 'ark')}-{task_id[:8]}{ext}",
        )
        info = json.dumps(
            {
                "profile": chosen.name,
                "base_url": chosen.base_url,
                "model": payload["model"],
                "task_id": task_id,
                "path": str(path),
                "resolution": resolution,
                "ratio": ratio,
                "duration": duration,
            },
            ensure_ascii=False,
        )
        if HAS_VIDEO_TYPE:
            return (VideoFromFile(str(path)), info)
        return (str(path),)


__all__ = ["ArkVideo", "VIDEO_MODELS", "MODES", "build_content"]
