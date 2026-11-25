"""ComfyUI custom nodes for Volcengine Ark and OpenAI-compatible image APIs.

Three nodes, one responsibility each:

- `ArkImage`   — Seedream on Volcengine Ark (standard / Agent Plan surfaces)
- `OpenAIImage` — any OpenAI-compatible image endpoint (third-party relays, /v1)
- `ArkVideo`   — Seedance on Volcengine Ark (video is Ark-only)

Connections live in this folder's `config.json`, split into an `ark` section and
an `openai` section, and are entered through ComfyUI's own Settings dialog.
"""
from __future__ import annotations

from .ark.routes import register_routes
from .nodes.image import ArkImage, OpenAIImage
from .nodes.video import ArkVideo

NODE_CLASS_MAPPINGS = {
    "ArkImage": ArkImage,
    "OpenAIImage": OpenAIImage,
    "ArkVideo": ArkVideo,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "ArkImage": "图片生成 · 方舟 Seedream（Ark Flex）",
    "OpenAIImage": "图片生成 · OpenAI 兼容（Ark Flex）",
    "ArkVideo": "视频生成 · Seedance（火山方舟）",
}

#: Serves web/arkflex_settings.js — the settings entries in ComfyUI's dialog.
WEB_DIRECTORY = "./web"

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS", "WEB_DIRECTORY"]

print("[ArkFlex] 已加载：ArkImage / OpenAIImage / ArkVideo（设置里分「方舟 Ark」「OpenAI 兼容」两页）")

# The Settings dialog posts values here so they land in this folder, not in
# ComfyUI's global settings file. Outside ComfyUI (unit tests) this is a no-op.
try:
    register_routes()
except Exception as error:  # pragma: no cover - depends on the host
    print(f"[ArkFlex] 设置接口未注册（不影响节点）：{error}")
