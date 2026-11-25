"""Image generation, split by provider.

`ArkImage` talks to Volcengine Ark (Seedream) and only offers Ark surfaces;
`OpenAIImage` talks to any OpenAI-compatible image endpoint and takes its
connection from the plugin settings (`OpenAI 兼容 → 连接`), with per-node
overrides. They share the payload builder, the response decoder and the
multipart `/images/edits` path — but no dropdown mixes the two providers.
"""
from __future__ import annotations

import base64
import io
import json
import urllib.request
from dataclasses import replace
from typing import Any

from ..ark.config import ARK, CUSTOM, OPENAI, profile_names, resolve
from ..ark.errors import ArkError
from .common import (
    COMMON_OPTIONS,
    PROFILE_INPUTS,
    client_for,
    merge_extra,
    model_id,
    tensor_to_png,
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

REFS_MODE_OPTIONS = ["跟随设置 / follow", "json", "multipart", "none"]


def size_value(label: str) -> str:
    """`"1280x720 (16:9)"` -> `"1280x720"`."""
    head = (label or "").split(" ")[0]
    width, _, height = head.partition("x")
    if not (width.isdigit() and height.isdigit()):
        raise ArkError(f"无法解析尺寸：{label}")
    return f"{width}x{height}"


def resolve_size(label: str, width: int, height: int, *, kind: str = "ark") -> str:
    """A `WxH` string from either the explicit width/height or the preset.

    Explicit dimensions exist for callers that compute them per aspect ratio
    (the `dsh-short-video-studio` manifests inject `width`/`height` of the
    frame). Ark itself insists on multiples of 16; other endpoints do not, so the
    check is dialect-aware rather than universal.
    """
    w, h = int(width), int(height)
    if w > 0 and h > 0:
        if kind == ARK and (w % 16 or h % 16):
            raise ArkError(f"火山方舟要求宽高为 16 的倍数（现在是 {w}x{h}）；可用画布比例推导的尺寸。")
        if w < 64 or h < 64:
            raise ArkError(f"尺寸太小：{w}x{h}")
        return f"{w}x{h}"
    if w > 0 or h > 0:
        raise ArkError("width / height 要么都填（>0），要么都留 0 用 size 预设。")
    return size_value(label)


def payload_for(
    *,
    model: str,
    prompt: str,
    size: str,
    watermark: bool | None = None,
    seed: int = -1,
    refs: list[Any] | None = None,
    provider: str = ARK,
) -> dict[str, Any]:
    """The request body for one image call (JSON dialect).

    `watermark` is an Ark field and `response_format` is an Ark/relay field; both
    are left out for an OpenAI endpoint, which may reject unknown fields.
    """
    body: dict[str, Any] = {"model": model, "prompt": prompt, "size": size}
    if provider == ARK:
        body["response_format"] = "url"
    if watermark is not None:
        body["watermark"] = bool(watermark)
    if int(seed) >= 0:
        body["seed"] = int(seed)
    usable = [image for image in (refs or []) if image is not None]
    if usable:
        from .common import tensor_to_data_url

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


def _generate(
    client,
    endpoint,
    *,
    prompt: str,
    model: str,
    size: str,
    count: int,
    refs: list[Any],
    extra_json: str,
    watermark: bool | None,
    timeout: int,
    seed: int,
) -> list[bytes]:
    """Run one call (or `count` calls), returning the raw image bytes."""
    if refs and endpoint.refs_mode == "none":
        raise ArkError(f"连接「{endpoint.name}」不允许参考图（refs_mode=none）。")
    blobs: list[bytes] = []
    if refs and endpoint.refs_mode == "multipart":
        fields = {"model": model, "prompt": prompt, "size": size, "n": str(count)}
        files = [(f"ref{index}.png", *tensor_to_png(image)) for index, image in enumerate(refs)]
        result = client.images_edits(fields, files, timeout=float(timeout))
        blobs.extend(decode_images(result))
        return blobs
    for index in range(count):
        # Ask N times instead of relying on a sequential flag only some Seedream
        # versions honour; the seed steps so the calls differ.
        call_seed = int(seed) + index if int(seed) >= 0 else -1
        body = payload_for(
            model=model,
            prompt=prompt,
            size=size,
            watermark=watermark,
            seed=call_seed,
            refs=refs,
            provider=endpoint.provider,
        )
        body = merge_extra(body, extra_json)
        result = client.post("/images/generations", body, timeout=float(timeout))
        blobs.extend(decode_images(result))
    return blobs


class ArkImage:
    """Image generation on Volcengine Ark (Seedream), either official surface."""

    CATEGORY = "Ark / 火山方舟"
    FUNCTION = "generate"
    RETURN_NAMES = ("images", "info")
    RETURN_TYPES = ("IMAGE", "STRING")

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, Any]:
        from ..ark.config import ark_models, loaded_config

        default_model = ark_models(loaded_config())["image"]
        options = IMAGE_MODELS if default_model in IMAGE_MODELS else [default_model, *IMAGE_MODELS]
        return {
            "required": {
                "profile": PROFILE_INPUTS["profile"],
                "prompt": ("STRING", {"default": "", "multiline": True}),
                "model": (options, {"default": default_model}),
                "size": (SIZES, {"default": SIZES[0]}),
                "width": ("INT", {"default": 0, "min": 0, "max": 4096,
                                  "tooltip": "0 = 用 size 预设；由流程按画布比例推导时填这里（两者都要 >0）。"}),
                "height": ("INT", {"default": 0, "min": 0, "max": 4096}),
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
        width: int,
        height: int,
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
        client, endpoint = client_for(
            ARK,
            kind="image",
            profile=profile,
            base_url_override=base_url_override,
            api_key_override=api_key_override,
        )
        model_name = model_id(model, custom_model)
        pixels = resolve_size(size, width, height, kind=ARK)
        refs = [image for image in (image1, image2, image3, image4) if image is not None]
        if refs and endpoint.refs_mode == "none":
            raise ArkError(f"profile「{endpoint.name}」不允许参考图（refs_mode=none）。")
        blobs = _generate(
            client,
            endpoint,
            prompt=prompt,
            model=model_name,
            size=pixels,
            count=max(1, int(max_images)),
            refs=refs,
            extra_json=extra_json,
            watermark=bool(watermark),
            timeout=timeout,
            seed=seed,
        )
        info = json.dumps(
            {
                "provider": ARK,
                "profile": endpoint.name,
                "base_url": endpoint.base_url,
                "model": model_name,
                "size": pixels,
                "count": len(blobs),
            },
            ensure_ascii=False,
        )
        return (blobs_to_tensor(blobs), info)


class OpenAIImage:
    """Image generation on any OpenAI-compatible endpoint.

    The connection comes from the plugin settings (`OpenAI 兼容 → 连接`); the node
    only carries per-call overrides, so no key has to be embedded in a workflow.
    """

    CATEGORY = "Ark / 火山方舟"
    FUNCTION = "generate"
    RETURN_NAMES = ("images", "info")
    RETURN_TYPES = ("IMAGE", "STRING")

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, Any]:
        from ..ark.config import loaded_config, openai_endpoints, openai_model

        known = openai_endpoints(loaded_config())
        entry = next(iter(known.values()), None)
        base = entry.base_url if entry else ""
        model = openai_model(loaded_config())
        return {
            "required": {
                "prompt": ("STRING", {"default": "", "multiline": True}),
                "model": ("STRING", {"default": model, "tooltip": "接口方的模型名，例如 gpt-image-2.5-sunburst-vip。"}),
                "size": ("STRING", {"default": "1024x1024", "tooltip": "也常写作 1024x1536；部分接口只接受固定尺寸。"}),
                "width": ("INT", {"default": 0, "min": 0, "max": 4096,
                                  "tooltip": "两者都 >0 时覆盖 size（由画布比例推导时用）。"}),
                "height": ("INT", {"default": 0, "min": 0, "max": 4096}),
                "max_images": ("INT", {"default": 1, "min": 1, "max": 4}),
                "base_url": ("STRING", {"default": base, "tooltip": "留空 = 用插件设置里的 OpenAI 兼容地址。"}),
                "api_key": ("STRING", {"default": "", "tooltip": "留空 = 用插件设置里的 Key；填了只对本节点生效。"}),
                "refs_mode": (REFS_MODE_OPTIONS, {"default": REFS_MODE_OPTIONS[0],
                                                  "tooltip": "参考图怎么送：跟随设置 / json（data URL）/ multipart（/images/edits 上传）/ none。"}),
                "seed": COMMON_OPTIONS["seed"],
                "timeout": COMMON_OPTIONS["timeout"],
                "extra_json": COMMON_OPTIONS["extra_json"],
            },
            "optional": {
                "image1": ("IMAGE",),
                "image2": ("IMAGE",),
                "image3": ("IMAGE",),
                "image4": ("IMAGE",),
            },
        }

    def generate(
        self,
        prompt: str,
        model: str,
        size: str,
        width: int,
        height: int,
        max_images: int,
        base_url: str,
        api_key: str,
        refs_mode: str,
        seed: int,
        timeout: int,
        extra_json: str,
        image1: Any = None,
        image2: Any = None,
        image3: Any = None,
        image4: Any = None,
    ):
        client, endpoint = client_for(
            OPENAI,
            kind="image",
            base_url_override=base_url,
            api_key_override=api_key,
        )
        mode = refs_mode if refs_mode in ("json", "multipart", "none") else endpoint.refs_mode
        endpoint = replace(endpoint, refs_mode=mode)
        model_name = model_id(model, "")
        pixels = resolve_size(size, width, height, kind=OPENAI)
        refs = [image for image in (image1, image2, image3, image4) if image is not None]
        blobs = _generate(
            client,
            endpoint,
            prompt=prompt,
            model=model_name,
            size=pixels,
            count=max(1, int(max_images)),
            refs=refs,
            extra_json=extra_json,
            watermark=None,
            timeout=timeout,
            seed=seed,
        )
        info = json.dumps(
            {
                "provider": OPENAI,
                "profile": endpoint.name,
                "base_url": endpoint.base_url,
                "refs_mode": endpoint.refs_mode,
                "model": model_name,
                "size": pixels,
                "count": len(blobs),
            },
            ensure_ascii=False,
        )
        return (blobs_to_tensor(blobs), info)


__all__ = [
    "ArkImage",
    "OpenAIImage",
    "IMAGE_MODELS",
    "SIZES",
    "REFS_MODE_OPTIONS",
    "payload_for",
    "decode_images",
    "size_value",
    "resolve_size",
]
