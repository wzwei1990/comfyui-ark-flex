"""Persistence for the Settings dialog: one file, inside this pack's folder.

ComfyUI has no uninstall hook, so anything kept in `comfy.settings.json` would
outlive deleting the node folder. The dialog therefore only *posts* here; this
module writes `custom_nodes/ComfyUI-ArkFlex/config.json`, and the dialog then
shows a saved marker instead of the secret. Uninstalling removes the key with
the folder.

The file is split the same way the dialog is: an `ark` section and an `openai`
section, so a relay's address cannot be typed into an Ark field.
"""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

from .config import (
    ARK_PLAN,
    ARK_STANDARD,
    CONFIG_PATH,
    OPENAI_PROFILE,
    REFS_MODES,
    migrate,
    openai_endpoints,
    ark_endpoints,
)

NODE_DIR = CONFIG_PATH.parent


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


def _section(config: dict[str, Any], name: str) -> dict[str, Any]:
    value = config.get(name)
    if not isinstance(value, dict):
        value = {}
        config[name] = value
    return value


def write_settings(
    *,
    ark_standard: str | None = None,
    ark_plan: str | None = None,
    openai_base_url: str | None = None,
    openai_api_key: str | None = None,
    openai_refs_mode: str | None = None,
    openai_model: str | None = None,
    image_default: str | None = None,
    video_default: str | None = None,
    path: Path | None = None,
) -> dict[str, Any]:
    """Store any subset of the settings; `None` leaves a value alone.

    An empty string clears a value. Defaults must name a configured profile — a
    typo there would quietly send calls to the wrong surface, so it is rejected
    instead of stored.
    """
    target = Path(path) if path is not None else config_path()
    config = migrate(read_config(target))

    if openai_refs_mode is not None and openai_refs_mode not in REFS_MODES:
        raise ValueError(f"refs_mode 只能是 {' / '.join(REFS_MODES)}")

    if ark_standard is not None or ark_plan is not None:
        section = _section(config, "ark")
        for name, value in ((ARK_STANDARD, ark_standard), (ARK_PLAN, ark_plan)):
            if value is None:
                continue
            entry = section.get(name)
            if not isinstance(entry, dict):
                entry = {}
                section[name] = entry
            text = value.strip()
            if text:
                entry["api_key"] = text
            else:
                entry.pop("api_key", None)

    if any(v is not None for v in (openai_base_url, openai_api_key, openai_refs_mode, openai_model)):
        section = _section(config, "openai")
        entry = section.get(OPENAI_PROFILE)
        if not isinstance(entry, dict):
            entry = {}
            section[OPENAI_PROFILE] = entry
        for key, value in (
            ("base_url", openai_base_url),
            ("api_key", openai_api_key),
            ("refs_mode", openai_refs_mode),
            ("model", openai_model),
        ):
            if value is None:
                continue
            text = value.strip()
            if key == "refs_mode":
                entry["refs_mode"] = text or "json"
            elif text:
                entry[key] = text
            else:
                entry.pop(key, None)

    if image_default is not None or video_default is not None:
        known = set(ark_endpoints(config)) | set(openai_endpoints(config))
        section = _section(config, "defaults")
        for kind, value in (("image", image_default), ("video", video_default)):
            if value is None:
                continue
            text = value.strip()
            if text and text not in known:
                raise ValueError(f"defaults.{kind} 必须是已配置的 profile（{', '.join(sorted(known))}）")
            section[kind] = text or ARK_STANDARD

    _write_atomic(target, config)
    return presence(target)


def presence(path: Path | None = None) -> dict[str, Any]:
    """What the dialog can show without echoing a secret."""
    config = migrate(read_config(path))
    ark = ark_endpoints(config)
    openai = openai_endpoints(config)
    entry = openai.get(OPENAI_PROFILE)
    return {
        "ark": {
            "standard": bool(ark.get(ARK_STANDARD) and ark[ARK_STANDARD].api_key),
            "agentPlan": bool(ark.get(ARK_PLAN) and ark[ARK_PLAN].api_key),
        },
        "openai": {
            "baseUrl": entry.base_url if entry else "",
            "apiKey": bool(entry and entry.api_key),
            "refsMode": entry.refs_mode if entry else "json",
            "model": entry.model if entry else "",
        },
        "defaults": {
            "image": (config.get("defaults") or {}).get("image") or ARK_STANDARD,
            "video": (config.get("defaults") or {}).get("video") or ARK_STANDARD,
        },
    }


__all__ = ["config_path", "read_config", "write_settings", "presence", "NODE_DIR"]
