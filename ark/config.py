"""Where a request goes, split into two provider namespaces.

Volcengine Ark and OpenAI-compatible relays are different products that happen to
share a request shape. Keeping them in one profile list made every dropdown a
mixed bag, so `config.json` has two sections:

    ark    : standard / agent-plan (the two official surfaces, keys not interchangeable)
    openai : any OpenAI-compatible image endpoint (base_url + key + refs_mode + model)

Resolution order, first hit wins:

    node override  ->  section entry  ->  ARK_API_KEY (ark only)  ->  built-in default

Only the two official Ark base URLs are built in; keys never are. A `profiles`
block from an earlier version is migrated on read, so nobody has to re-enter a
key by hand.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

STANDARD_BASE_URL = "https://ark.cn-beijing.volces.com/api/v3"
AGENT_PLAN_BASE_URL = "https://ark.cn-beijing.volces.com/api/plan/v3"

ARK_STANDARD = "standard"
ARK_PLAN = "agent-plan"
ARK_BASE_URLS = {ARK_STANDARD: STANDARD_BASE_URL, ARK_PLAN: AGENT_PLAN_BASE_URL}

#: The single OpenAI-compatible connection the Settings dialog edits.
OPENAI_PROFILE = "apiyi"

CUSTOM = "自定义 / custom"
ARK = "ark"
OPENAI = "openai"
REFS_MODES = ("json", "multipart", "none")

#: Initial model names for the Settings dialog; every one of them is editable.
ARK_IMAGE_MODEL_DEFAULT = "doubao-seedream-5-0-pro"
ARK_VIDEO_MODEL_DEFAULT = "doubao-seedance-2-5-flash-261115"
OPENAI_MODEL_DEFAULT = "gpt-image-2.6-sunburst"

NODE_DIR = Path(__file__).resolve().parent.parent
CONFIG_PATH = NODE_DIR / "config.json"
EXAMPLE_PATH = NODE_DIR / "config.example.json"


@dataclass(frozen=True)
class Endpoint:
    """One place to send a request, with the dialect it speaks."""

    name: str
    provider: str
    base_url: str
    api_key: str
    label: str = ""
    refs_mode: str = "json"
    model: str = ""

    @property
    def display(self) -> str:
        return self.label or self.name

    @property
    def is_ark(self) -> bool:
        return self.provider == ARK


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


def migrate(config: dict[str, Any]) -> dict[str, Any]:
    """Turn an older `profiles` block (with `kind`) into the two sections.

    Read-only: the file is rewritten on the next save. Ark entries keep their
    names (so `standard` / `agent-plan` land where the built-ins expect them) and
    everything `kind: openai` moves under `openai`. A superseded `profiles` block
    is dropped even when it sits next to the new sections — otherwise the file
    would hold two copies of every key.
    """
    def without_legacy(value: dict[str, Any]) -> dict[str, Any]:
        return {key: item for key, item in value.items() if key != "profiles"}

    if "ark" in config or "openai" in config:
        return without_legacy(config)
    old = config.get("profiles")
    if not isinstance(old, dict) or not old:
        return without_legacy(config)
    ark: dict[str, Any] = {}
    openai: dict[str, Any] = {}
    for name, entry in old.items():
        if not isinstance(entry, dict) or not isinstance(name, str):
            continue
        kind = entry.get("kind") if entry.get("kind") in (ARK, OPENAI) else (
            ARK if name in ARK_BASE_URLS else OPENAI
        )
        base = entry.get("base_url") if isinstance(entry.get("base_url"), str) else ""
        key = entry.get("api_key") if isinstance(entry.get("api_key"), str) else ""
        if kind == ARK:
            ark[name] = {"base_url": base, "api_key": key}
        else:
            mode = entry.get("refs_mode") if entry.get("refs_mode") in REFS_MODES else "json"
            openai[name] = {
                "base_url": base,
                "api_key": key,
                "refs_mode": mode,
                "model": entry.get("model") if isinstance(entry.get("model"), str) else "",
            }
    out = without_legacy(config)
    if ark:
        out["ark"] = ark
    if openai:
        out["openai"] = openai
    return out


def loaded_config() -> dict[str, Any]:
    """`config.json`, migrated in memory when it still has the old shape."""
    return migrate(raw_config())


def ark_endpoints(config: dict[str, Any] | None = None) -> dict[str, Endpoint]:
    """The two official surfaces, plus anything extra the user added under `ark`."""
    cfg = loaded_config() if config is None else migrate(config)
    out: dict[str, Endpoint] = {
        ARK_STANDARD: Endpoint(ARK_STANDARD, ARK, STANDARD_BASE_URL, "", "标准 API / Standard"),
        ARK_PLAN: Endpoint(ARK_PLAN, ARK, AGENT_PLAN_BASE_URL, "", "Agent Plan"),
    }
    section = cfg.get("ark")
    if isinstance(section, dict):
        for name, value in section.items():
            if not isinstance(name, str) or not isinstance(value, dict):
                continue
            base = value.get("base_url")
            key = value.get("api_key")
            if not isinstance(base, str) or not base.strip():
                base = ARK_BASE_URLS.get(name, STANDARD_BASE_URL)
            out[name] = Endpoint(
                name,
                ARK,
                base.strip().rstrip("/"),
                key.strip() if isinstance(key, str) else "",
                "标准 API / Standard" if name == ARK_STANDARD else ("Agent Plan" if name == ARK_PLAN else name),
            )
    return out


def openai_endpoints(config: dict[str, Any] | None = None) -> dict[str, Endpoint]:
    """Every OpenAI-compatible connection under `openai`."""
    cfg = loaded_config() if config is None else migrate(config)
    out: dict[str, Endpoint] = {}
    section = cfg.get("openai")
    if not isinstance(section, dict):
        return out
    for name, value in section.items():
        if not isinstance(name, str) or not isinstance(value, dict):
            continue
        base = value.get("base_url")
        if not isinstance(base, str) or not base.strip():
            continue
        mode = value.get("refs_mode") if value.get("refs_mode") in REFS_MODES else "json"
        out[name] = Endpoint(
            name,
            OPENAI,
            base.strip().rstrip("/"),
            (value.get("api_key") or "").strip() if isinstance(value.get("api_key"), str) else "",
            name,
            mode,
            value.get("model").strip() if isinstance(value.get("model"), str) and value.get("model").strip() else "",
        )
    return out


def endpoints(provider: str, config: dict[str, Any] | None = None) -> dict[str, Endpoint]:
    return ark_endpoints(config) if provider == ARK else openai_endpoints(config)


def profile_names(provider: str, config: dict[str, Any] | None = None) -> list[str]:
    """Names for a COMBO widget, custom last."""
    return [*endpoints(provider, config).keys(), CUSTOM]


def defaults(config: dict[str, Any] | None = None) -> dict[str, str]:
    """`defaults.image` / `defaults.video`: which profile name a new call prefers."""
    cfg = loaded_config() if config is None else migrate(config)
    raw = cfg.get("defaults")
    out = {"image": ARK_STANDARD, "video": ARK_STANDARD}
    if isinstance(raw, dict):
        for kind in ("image", "video"):
            value = raw.get(kind)
            if isinstance(value, str) and value.strip():
                out[kind] = value.strip()
    return out


def first_model(provider: str, config: dict[str, Any] | None = None) -> str:
    """A default model name for a free-text model widget."""
    if provider != OPENAI:
        return ""
    known = openai_endpoints(config)
    for endpoint in known.values():
        if endpoint.model:
            return endpoint.model
    return ""


def ark_models(config: dict[str, Any] | None = None) -> dict[str, str]:
    """`ark.image_model` / `ark.video_model`, with the built-in starting values."""
    cfg = loaded_config() if config is None else migrate(config)
    section = cfg.get("ark") if isinstance(cfg.get("ark"), dict) else {}
    out = {"image": ARK_IMAGE_MODEL_DEFAULT, "video": ARK_VIDEO_MODEL_DEFAULT}
    for kind in ("image", "video"):
        value = section.get(f"{kind}_model")
        if isinstance(value, str) and value.strip():
            out[kind] = value.strip()
    return out


def openai_model(config: dict[str, Any] | None = None) -> str:
    """The relay's default model, falling back to the shipped starting value."""
    for endpoint in openai_endpoints(config).values():
        if endpoint.model:
            return endpoint.model
    return OPENAI_MODEL_DEFAULT


def resolve(
    provider: str,
    *,
    profile: str | None = None,
    base_url_override: str | None = None,
    api_key_override: str | None = None,
    kind: str = "image",
    config: dict[str, Any] | None = None,
) -> Endpoint:
    """The endpoint one node call should use.

    `kind` (`image` / `video`) only picks the fallback when the node names no
    profile; `provider` decides which section the names are looked up in.
    """
    cfg = loaded_config() if config is None else migrate(config)
    known = endpoints(provider, cfg)
    chosen = (profile or "").strip() or defaults(cfg).get(kind, ARK_STANDARD)
    if chosen == CUSTOM or chosen not in known:
        entry = Endpoint(CUSTOM, provider, "", "", "自定义 / Custom")
        if chosen != CUSTOM:
            # The default may name a profile of the *other* provider (e.g.
            # `image: apiyi` while this node is an Ark node): fall back to this
            # provider's own first entry instead of sending an Ark key to a relay.
            fallback = chosen if chosen in known else next(iter(known), CUSTOM)
            entry = known.get(fallback, entry)
    else:
        entry = known[chosen]

    base = (base_url_override or "").strip() or entry.base_url
    if not base and provider == ARK:
        base = ARK_BASE_URLS.get(chosen, STANDARD_BASE_URL)
    base = base.rstrip("/")

    key = (api_key_override or "").strip() or entry.api_key
    if not key and provider == ARK:
        key = os.environ.get("ARK_API_KEY", "").strip()
    return Endpoint(entry.name, provider, base, key, entry.label or entry.name, entry.refs_mode, entry.model)


__all__ = [
    "AGENT_PLAN_BASE_URL",
    "ARK",
    "ARK_IMAGE_MODEL_DEFAULT",
    "ARK_PLAN",
    "ARK_STANDARD",
    "ARK_BASE_URLS",
    "ARK_VIDEO_MODEL_DEFAULT",
    "CONFIG_PATH",
    "CUSTOM",
    "Endpoint",
    "OPENAI",
    "OPENAI_MODEL_DEFAULT",
    "OPENAI_PROFILE",
    "REFS_MODES",
    "STANDARD_BASE_URL",
    "ark_endpoints",
    "ark_models",
    "defaults",
    "endpoints",
    "first_model",
    "loaded_config",
    "migrate",
    "openai_endpoints",
    "openai_model",
    "profile_names",
    "raw_config",
    "resolve",
]
