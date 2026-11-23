"""Where the key actually lives: inside this pack's own folder.

ComfyUI has no uninstall hook, so anything kept in ComfyUI's global
`comfy.settings.json` survives the removal of the node folder — you delete the
pack and a plaintext key is still sitting in the user settings file.

So the Settings dialog is only an input surface: the web extension posts what
you type to `/arkflex/settings`, this module writes it into
`custom_nodes/ComfyUI-ArkFlex/config.json`, and the extension then clears the
ComfyUI-side copy. Uninstalling is literally deleting the folder.
"""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

NODE_DIR = Path(__file__).resolve().parent.parent
CONFIG_PATH = NODE_DIR / "config.json"

STANDARD = "standard"
AGENT_PLAN = "agent-plan"

PROFILE_URLS = {
    STANDARD: "https://ark.cn-beijing.volces.com/api/v3",
    AGENT_PLAN: "https://ark.cn-beijing.volces.com/api/plan/v3",
}


def config_path() -> Path:
    return CONFIG_PATH


def read_config(path: Path | None = None) -> dict[str, Any]:
    target = Path(path) if path is not None else config_path()
    try:
        with target.open("r", encoding="utf-8") as handle:
            value = json.load(handle)
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError):
        return {}


def _write_atomic(path: Path, value: dict[str, Any]) -> None:
    """Write beside the target, then replace: a crash never half-writes a key."""
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, tmp = tempfile.mkstemp(prefix=".config-", suffix=".json", dir=str(path.parent))
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def write_keys(
    standard: str | None = None,
    agent_plan: str | None = None,
    image_default: str | None = None,
    video_default: str | None = None,
    path: Path | None = None,
) -> dict[str, Any]:
    """Store keys and/or the per-kind default surface in `config.json`.

    `None` means "don't touch this one"; an empty string clears a key. Defaults
    must name a known surface — a typo there would silently send images to the
    wrong URL, so it is rejected instead. Returns presence plus the defaults,
    never the secrets.
    """
    target = Path(path) if path is not None else config_path()
    for label, value in (("image", image_default), ("video", video_default)):
        if value is not None and value not in PROFILE_URLS:
            raise ValueError(f"defaults.{label} must be one of {', '.join(PROFILE_URLS)}")

    config = read_config(target)
    profiles = config.get("profiles")
    if not isinstance(profiles, dict):
        profiles = {}
        config["profiles"] = profiles

    for name, value in ((STANDARD, standard), (AGENT_PLAN, agent_plan)):
        if value is None:
            continue
        entry = profiles.get(name)
        if not isinstance(entry, dict):
            entry = {"base_url": PROFILE_URLS[name]}
            profiles[name] = entry
        entry.setdefault("base_url", PROFILE_URLS[name])
        text = value.strip()
        if text:
            entry["api_key"] = text
        else:
            entry.pop("api_key", None)

    defaults = config.get("defaults")
    if not isinstance(defaults, dict):
        defaults = {}
        config["defaults"] = defaults
    for label, value in (("image", image_default), ("video", video_default)):
        if value is not None:
            defaults[label] = value
    defaults.setdefault("image", STANDARD)
    defaults.setdefault("video", STANDARD)

    _write_atomic(target, config)
    return {"keys": key_presence(target), "defaults": read_defaults(target)}


def read_defaults(path: Path | None = None) -> dict[str, str]:
    """The per-kind default surface names, with the built-in fallback filled in."""
    defaults = read_config(path).get("defaults")
    out = {"image": STANDARD, "video": STANDARD}
    if isinstance(defaults, dict):
        for kind in ("image", "video"):
            value = defaults.get(kind)
            if isinstance(value, str) and value in PROFILE_URLS:
                out[kind] = value
    return out


def key_presence(path: Path | None = None) -> dict[str, bool]:
    """Whether each surface has a key, without returning the key itself."""
    profiles = read_config(path).get("profiles")
    out = {"standard": False, "agentPlan": False}
    if isinstance(profiles, dict):
        for name, label in ((STANDARD, "standard"), (AGENT_PLAN, "agentPlan")):
            entry = profiles.get(name)
            if isinstance(entry, dict) and isinstance(entry.get("api_key"), str) and entry["api_key"].strip():
                out[label] = True
    return out


__all__ = ["config_path", "read_config", "write_keys", "key_presence", "read_defaults", "NODE_DIR", "PROFILE_URLS"]
