"""ComfyUI custom nodes for Volcengine Ark — standard API and Agent Plan.

One package, two surfaces: each node picks a *profile* (base URL + key), so the
image nodes can use the standard surface while the video nodes use Agent Plan,
or the other way round. The two Ark surfaces share request bodies but not keys.
"""
from __future__ import annotations

from .ark.routes import register_routes
from .nodes.image import ArkImage
from .nodes.video import ArkVideo

NODE_CLASS_MAPPINGS = {
    "ArkImage": ArkImage,
    "ArkVideo": ArkVideo,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "ArkImage": "Ark 图片 · Seedream（火山方舟）",
    "ArkVideo": "Ark 视频 · Seedance（火山方舟）",
}

#: Serves web/arkflex_settings.js — the two key fields in ComfyUI's Settings dialog.
WEB_DIRECTORY = "./web"

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS", "WEB_DIRECTORY"]

print("[ArkFlex] 已加载：ArkImage / ArkVideo（profile 可选 standard 或 agent-plan）")

# The Settings dialog posts the key here so it lands in this folder, not in
# ComfyUI's global settings file. Outside ComfyUI (unit tests) this is a no-op.
try:
    register_routes()
except Exception as error:  # pragma: no cover - depends on the host
    print(f"[ArkFlex] 设置接口未注册（不影响节点）：{error}")
