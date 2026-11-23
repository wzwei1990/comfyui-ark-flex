"""Pieces every Ark node shares: profile widgets, tensors, save paths."""
from __future__ import annotations

import base64
import io
import json
import os
import tempfile
from pathlib import Path
from typing import Any

from ..ark.config import CUSTOM, profile_names, resolve
from ..ark.errors import ArkError

MAX_SEED = 2**31 - 1

PROFILE_INPUTS = {
    "profile": (profile_names(), {"default": "standard", "tooltip": "选择接入面：standard (/api/v3) 或 agent-plan (/api/plan/v3)；两者 Key 不通用。"}),
    "base_url_override": ("STRING", {"default": "", "tooltip": "留空则用 profile 的地址；填了则覆盖（例如自己代理的兼容地址）。"}),
    "api_key_override": ("STRING", {"default": "", "tooltip": "留空则用 config.json / ARK_API_KEY；填了则只对本节点生效。"}),
}

COMMON_OPTIONS = {
    "seed": ("INT", {"default": -1, "min": -1, "max": MAX_SEED, "tooltip": "-1 表示不传，由服务端随机。"}),
    "watermark": ("BOOLEAN", {"default": False}),
    "extra_json": ("STRING", {"default": "", "multiline": True, "tooltip": "可选的 JSON，浅合并进请求体，用于试验新参数而不用改代码。"}),
    "timeout": ("INT", {"default": 900, "min": 30, "max": 7200, "tooltip": "视频任务最长等待秒数。"}),
    "poll_seconds": ("INT", {"default": 2, "min": 1, "max": 30}),
}


def client_for(kind: str, **kwargs: Any):
    """Build an `ArkClient` from a node's inputs, explaining a missing key."""
    from ..ark.client import ArkClient

    profile = resolve(kind, **{key: kwargs.get(key) for key in ("profile", "base_url_override", "api_key_override")})
    if not profile.api_key:
        raise ArkError(
            "没有 API Key：把 Key 填进 config.json 的对应 profile、设置环境变量 ARK_API_KEY，"
            "或在本节点填 api_key_override。方舟标准入口与 Agent Plan 入口的 Key 不通用。"
        )
    return ArkClient(profile.base_url, profile.api_key), profile


def model_id(model: str, custom_model: str) -> str:
    """`custom_model` wins, so a model missing from the list still works."""
    chosen = (custom_model or "").strip() or (model or "").strip()
    if not chosen:
        raise ArkError("没有模型：请选择 model，或在 custom_model 里直接填模型 / 端点 id。")
    return chosen


def merge_extra(payload: dict, extra_json: str) -> dict:
    """Shallow-merge a user's JSON over the built payload."""
    text = (extra_json or "").strip()
    if not text:
        return payload
    try:
        extra = json.loads(text)
    except ValueError as error:
        raise ArkError(f"extra_json 不是合法 JSON：{error}") from None
    if not isinstance(extra, dict):
        raise ArkError("extra_json 必须是一个 JSON 对象，例如 {\"some_flag\": true}。")
    payload.update(extra)
    return payload


def tensor_to_data_url(image: Any, fmt: str = "PNG") -> str:
    """Encode one ComfyUI IMAGE tensor (1,H,W,C float 0..1) as a data URL.

    Ark accepts a public URL or a data URL for reference media; local images
    therefore need no upload endpoint.
    """
    try:
        import numpy as np
        from PIL import Image
        import torch  # noqa: F401  (ComfyUI always provides it)
    except Exception as error:  # pragma: no cover - depends on the host
        raise ArkError(f"编码图片失败（缺少 torch/numpy/Pillow）：{error}") from None
    array = image[0] if getattr(image, "ndim", 0) == 4 else image
    if getattr(array, "requires_grad", False):
        array = array.detach()
    pixels = (array.mul(255).clamp(0, 255).to("cpu", "uint8").numpy() if hasattr(array, "mul")
              else np.clip(array, 0, 1) * 255)
    buffer = io.BytesIO()
    Image.fromarray(np.asarray(pixels, dtype=np.uint8)).save(buffer, format=fmt)
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    mime = "image/png" if fmt.upper() == "PNG" else "image/jpeg"
    return f"data:{mime};base64,{encoded}"


def output_dir(kind: str) -> Path:
    """ComfyUI's output folder when running inside it, else a temp folder."""
    try:
        import folder_paths  # type: ignore

        root = Path(folder_paths.get_output_directory())
    except Exception:
        root = Path(tempfile.gettempdir()) / "comfyui-output"
    target = root / "ark" / kind
    target.mkdir(parents=True, exist_ok=True)
    return target


def safe_stem(value: str, fallback: str = "ark") -> str:
    keep = [ch for ch in (value or "") if ch.isalnum() or ch in "-_."]
    text = "".join(keep).strip("._-")
    return text[:60] or fallback


def video_ext(url: str, output_format: str) -> str:
    suffix = os.path.splitext(url.split("?")[0])[1].lower()
    if suffix in (".mp4", ".mov", ".webm"):
        return suffix
    return ".mov" if (output_format or "").lower() == "mov" else ".mp4"


__all__ = [
    "CUSTOM",
    "PROFILE_INPUTS",
    "COMMON_OPTIONS",
    "client_for",
    "model_id",
    "merge_extra",
    "tensor_to_data_url",
    "output_dir",
    "safe_stem",
    "video_ext",
]
