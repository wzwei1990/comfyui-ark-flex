"""Image generation on Volcengine Ark (Seedream family)."""
from __future__ import annotations

import base64
import io
import json
import urllib.request
from typing import Any

from ..ark.errors import ArkError
from .common import (
    COMMON_OPTIONS,
    PROFILE_INPUTS,
    client_for,
    merge_extra,
    model_id,
    tensor_to_data_url,
)

IMAGE_MODELS = [
    "doubao-seedream-5-0-pro",
    "doubao-seedream-5-0-lite",
    "doubao-seedream-4-5",
    "doubao-seedream-4-0",
    "doubao-seedream-3-0-t2i",
]

#: Presets are pixels, not labels: Ark bills by pixel steps, and a square 2048
#: would cross a price boundary that 2048x1152 does not.
SIZES = [
    "1024x1024 (1:1)",
    "1152x864 (4:3)",
    "864x1152 (3:4)",
    "1280x720 (16:9)",
    "720x1280 (9:16)",
    "2048x1152 (16:9)",
    "1152x2048 (9:16)",
    "1600x1600 (1:1)",
]


def size_value(label: str) -> str:
    """`"1280x720 (16:9)"` -> `"1280x720"`."""
    head = (label or "").split(" ")[0]
    width, _, height = head.partition("x")
    if not (width.isdigit() and height.isdigit()):
        raise ArkError(f"无法解析尺寸：{label}")
    return f"{width}x{height}"


def payload_for(
    *,
    model: str,
    prompt: str,
    size: str,
    watermark: bool,
    seed: int,
    refs: list[Any] | None = None,
    sequential: bool = False,
) -> dict[str, Any]:
    """The request body for one image call."""
    body: dict[str, Any] = {
        "model": model,
        "prompt": prompt,
        "size": size,
        "response_format": "url",
        "watermark": bool(watermark),
    }
    if int(seed) >= 0:
        body["seed"] = int(seed)
    if sequential:
        body["sequential_image_generation"] = "auto"
    usable = [image for image in (refs or []) if image is not None]
    if usable:
        body["image"] = [tensor_to_data_url(image) for image in usable]
    return body


def decode_images(result: dict) -> list[bytes]:
    """Each produced image as bytes, from either `b64_json` or `url`."""
    rows = result.get("data")
    if not isinstance(rows, list) or not rows:
        raise ArkError(f"图片接口没有返回 data：{json.dumps(result, ensure_ascii=False)[:300]}")
    blobs: list[bytes] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        if isinstance(row.get("b64_json"), str) and row["b64_json"]:
            blobs.append(base64.b64decode(row["b64_json"]))
            continue
        url = row.get("url")
        if not isinstance(url, str) or not url:
            continue
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"Accept": "*/*"}), timeout=300) as response:
                blobs.append(response.read())
        except Exception as error:
            raise ArkError(f"下载生成的图片失败：{error}（{url}）") from None
    if not blobs:
        raise ArkError("图片接口返回成功，但没有可用的图片数据（b64_json / url 都为空）。")
    return blobs


def blobs_to_tensor(blobs: list[bytes]):
    """Decode to a ComfyUI IMAGE batch, resizing later pictures to the first."""
    try:
        import numpy as np
        import torch
        from PIL import Image
    except Exception as error:  # pragma: no cover - depends on the host
        raise ArkError(f"解码图片失败（缺少 torch/numpy/Pillow）：{error}") from None

    frames = []
    base_size = None
    for blob in blobs:
        picture = Image.open(io.BytesIO(blob)).convert("RGB")
        if base_size is None:
            base_size = picture.size
        elif picture.size != base_size:
            picture = picture.resize(base_size, Image.LANCZOS)
        array = np.asarray(picture, dtype=np.float32) / 255.0
        frames.append(torch.from_numpy(array)[None, ...])
    return torch.cat(frames, dim=0)


class ArkImage:
    """Seedream generation, with optional reference images."""

    CATEGORY = "Ark / 火山方舟"
    FUNCTION = "generate"
    RETURN_NAMES = ("images", "info")
    RETURN_TYPES = ("IMAGE", "STRING")

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, Any]:
        return {
            "required": {
                "profile": PROFILE_INPUTS["profile"],
                "prompt": ("STRING", {"default": "", "multiline": True}),
                "model": (IMAGE_MODELS, {"default": IMAGE_MODELS[0]}),
                "size": (SIZES, {"default": SIZES[0]}),
                "max_images": ("INT", {"default": 1, "min": 1, "max": 4}),
                "base_url_override": PROFILE_INPUTS["base_url_override"],
                "api_key_override": PROFILE_INPUTS["api_key_override"],
                "seed": COMMON_OPTIONS["seed"],
                "watermark": COMMON_OPTIONS["watermark"],
                "timeout": COMMON_OPTIONS["timeout"],
                "extra_json": COMMON_OPTIONS["extra_json"],
            },
            "optional": {
                "custom_model": ("STRING", {"default": "", "tooltip": "填了就用它（端点 id 或新模型名）。"}),
                "image1": ("IMAGE",),
                "image2": ("IMAGE",),
                "image3": ("IMAGE",),
                "image4": ("IMAGE",),
            },
        }

    def generate(
        self,
        profile: str,
        prompt: str,
        model: str,
        size: str,
        max_images: int,
        base_url_override: str,
        api_key_override: str,
        seed: int,
        watermark: bool,
        timeout: int,
        extra_json: str,
        custom_model: str = "",
        image1: Any = None,
        image2: Any = None,
        image3: Any = None,
        image4: Any = None,
    ):
        client, chosen = client_for(
            "image",
            profile=profile,
            base_url_override=base_url_override,
            api_key_override=api_key_override,
        )
        model_name = model_id(model, custom_model)
        count = max(1, int(max_images))
        refs = [image1, image2, image3, image4]

        blobs: list[bytes] = []
        for index in range(count):
            # Ask N times instead of relying on a sequential-mode flag that only
            # some Seedream versions honour; the seed steps so the calls differ.
            call_seed = int(seed) + index if int(seed) >= 0 else -1
            body = payload_for(
                model=model_name,
                prompt=prompt,
                size=size_value(size),
                watermark=watermark,
                seed=call_seed,
                refs=refs,
            )
            body = merge_extra(body, extra_json)
            result = client.post("/images/generations", body, timeout=float(timeout))
            blobs.extend(decode_images(result))

        images = blobs_to_tensor(blobs)
        info = json.dumps(
            {
                "profile": chosen.name,
                "base_url": chosen.base_url,
                "model": model_name,
                "size": size_value(size),
                "count": len(blobs),
            },
            ensure_ascii=False,
        )
        return (images, info)


__all__ = ["ArkImage", "IMAGE_MODELS", "SIZES", "payload_for", "decode_images", "size_value"]
