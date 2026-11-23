"""Where a request goes: base URL + API key, resolved per call.

The two Volcengine Ark surfaces differ only in their base URL, and a key from
one is rejected by the other (403). So every node carries a *profile*: a named
pair of (base_url, api_key). Image and video pick their profile independently,
which is what makes "images on the standard surface, video on the plan" work.

Resolution order for each field, first hit wins:

    node override  ->  profile entry  ->  environment  ->  built-in default

Only the two official base URLs are built in; keys never are.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

#: The standard Ark surface.
STANDARD_BASE_URL = "https://ark.cn-beijing.volces.com/api/v3"
#: The Agent Plan surface (same request bodies, its own key).
AGENT_PLAN_BASE_URL = "https://ark.cn-beijing.volces.com/api/plan/v3"

NODE_DIR = Path(__file__).resolve().parent.parent
CONFIG_PATH = NODE_DIR / "config.json"
EXAMPLE_PATH = NODE_DIR / "config.example.json"

CUSTOM = "自定义 / custom"


@dataclass(frozen=True)
class Profile:
    """One (base_url, api_key) pair, by name."""

    name: str
    base_url: str
    api_key: str
    label: str = ""

    @property
    def display(self) -> str:
        return self.label or self.name


def _read_json(path: Path) -> dict[str, Any]:
    try:
        with path.open("r", encoding="utf-8") as handle:
            value = json.load(handle)
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError):
        return {}


def raw_config() -> dict[str, Any]:
    """`config.json` next to the node, or an empty dict."""
    return _read_json(CONFIG_PATH)


def profiles(config: dict[str, Any] | None = None) -> dict[str, Profile]:
    """Every configured profile, plus the two official surfaces as defaults.

    A `config.json` entry wins over the built-in one of the same name, so a user
    can pre-fill keys without repeating the URLs.
    """
    cfg = raw_config() if config is None else config
    out: dict[str, Profile] = {
        "standard": Profile("standard", STANDARD_BASE_URL, "", "标准 API / Standard"),
        "agent-plan": Profile("agent-plan", AGENT_PLAN_BASE_URL, "", "Agent Plan"),
    }
    entries = cfg.get("profiles")
    if isinstance(entries, dict):
        for name, value in entries.items():
            if not isinstance(value, dict) or not isinstance(name, str):
                continue
            base = value.get("base_url")
            key = value.get("api_key")
            label = value.get("label")
            if not isinstance(base, str) or not base.strip():
                continue
            out[name] = Profile(
                name,
                base.strip().rstrip("/"),
                key.strip() if isinstance(key, str) else "",
                label if isinstance(label, str) and label else name,
            )
    return out


def profile_names(config: dict[str, Any] | None = None) -> list[str]:
    """Names for a COMBO widget, custom last."""
    return [*profiles(config).keys(), CUSTOM]


def defaults(config: dict[str, Any] | None = None) -> dict[str, str]:
    """The per-kind default profile name (`defaults.image` / `defaults.video`)."""
    cfg = raw_config() if config is None else config
    raw = cfg.get("defaults")
    out = {"image": "standard", "video": "standard"}
    if isinstance(raw, dict):
        for kind in ("image", "video"):
            value = raw.get(kind)
            if isinstance(value, str) and value.strip():
                out[kind] = value.strip()
    return out


def resolve(
    kind: str,
    *,
    profile: str | None = None,
    base_url_override: str | None = None,
    api_key_override: str | None = None,
    config: dict[str, Any] | None = None,
) -> Profile:
    """The profile a single node call should use.

    `kind` is `image` or `video` and only selects the fallback default; the
    profile itself is whatever the node asked for. An explicit base URL override
    always wins, and a key override applies to the resolved profile.
    """
    cfg = raw_config() if config is None else config
    known = profiles(cfg)
    chosen = (profile or "").strip() or defaults(cfg).get(kind, "standard")
    if chosen == CUSTOM or chosen not in known:
        # The custom choice must carry its own URL; without one, fall back to the
        # kind's default profile rather than guessing.
        if chosen != CUSTOM:
            chosen = defaults(cfg).get(kind, "standard")
        entry = Profile(CUSTOM, "", "", "自定义 / Custom")
    else:
        entry = known[chosen]

    base = (base_url_override or "").strip() or entry.base_url
    if not base:
        # A custom choice without its own URL is the kind's default profile,
        # not a silent hop to the standard surface.
        fallback = defaults(cfg).get(kind, "standard")
        base = known.get(fallback, Profile(fallback, STANDARD_BASE_URL, "")).base_url
    key = (api_key_override or "").strip() or entry.api_key or os.environ.get("ARK_API_KEY", "").strip()
    if not key and entry.name == CUSTOM:
        # Same idea for the key: a custom URL with no key of its own uses the
        # default profile's key, which is what "custom base URL, usual account"
        # means in practice.
        fallback = defaults(cfg).get(kind, "standard")
        key = known.get(fallback, Profile(fallback, STANDARD_BASE_URL, "")).api_key
    return Profile(entry.name, base.rstrip("/"), key, entry.label or entry.name)
