"""Reading keys the way ComfyUI itself does: from the frontend settings file.

ComfyUI's own API nodes keep their key in a frontend setting, which persists to
`<user>/default/comfy.settings.json`. This pack registers two settings (see
`web/arkflex_settings.js`) and reads the same file, so the key is typed in the
Settings dialog instead of a config file.

Nothing here is required: a `config.json` profile or `ARK_API_KEY` works without
the settings file, and a missing file is an empty dict, not an error.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

#: Setting ids, shared with the web extension. Changing one breaks the pairing.
STANDARD_KEY_ID = "ArkFlex.StandardApiKey"
PLAN_KEY_ID = "ArkFlex.PlanApiKey"

PLAN_URL_HINT = "/api/plan/"

#: What the settings field shows after a key was saved into the pack folder.
#: It is not a secret, and it must never be sent to the API as one — the web
#: extension writes it, so the two strings have to match
#: (`web/arkflex_settings.js`).
SAVED_MARKER = "✅ 已保存到 config.json（卸载插件即清除）"


def user_settings_path() -> Path | None:
    """`<ComfyUI>/user/default/comfy.settings.json`, when ComfyUI is importable."""
    try:
        import folder_paths  # type: ignore

        return Path(folder_paths.get_user_directory()) / "default" / "comfy.settings.json"
    except Exception:
        return None


def read_settings(path: Path | None = None) -> dict[str, Any]:
    """Parse the settings file; absent or malformed reads as empty."""
    target = path if path is not None else user_settings_path()
    if target is None:
        return {}
    try:
        with Path(target).open("r", encoding="utf-8") as handle:
            value = json.load(handle)
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError):
        return {}


def key_for_profile(name: str, base_url: str, path: Path | None = None) -> str:
    """The key for one surface, from the Settings dialog.

    The profile name decides; a custom profile falls back to the URL, because a
    `/api/plan/` address can only use the Agent Plan key.
    """
    data = read_settings(path)
    plan = name == "agent-plan" or PLAN_URL_HINT in (base_url or "")
    value = data.get(PLAN_KEY_ID if plan else STANDARD_KEY_ID)
    if not isinstance(value, str):
        return ""
    text = value.strip()
    # The marker means "already saved into the pack folder"; it is not a key.
    if not text or text == SAVED_MARKER:
        return ""
    return text


__all__ = ["STANDARD_KEY_ID", "PLAN_KEY_ID", "user_settings_path", "read_settings", "key_for_profile"]
