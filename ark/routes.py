"""Two endpoints the Settings dialog talks to.

The key is typed in ComfyUI's Settings dialog, posted here, and written into this
pack's own `config.json`; the dialog then clears its copy. That keeps the
secret inside the node folder, so removing the folder removes the key too.
"""
from __future__ import annotations

from . import store

_SETTING_NAMES = ("standard", "agentPlan")
_DEFAULT_NAMES = ("imageDefault", "videoDefault")


def register_routes() -> bool:
    """Attach `/arkflex/settings` to ComfyUI's server; False outside ComfyUI."""
    try:
        from server import PromptServer  # type: ignore
    except Exception:
        return False
    server = getattr(PromptServer, "instance", None)
    if server is None or getattr(server, "_arkflex_routes", False):
        return False
    try:
        from aiohttp import web  # type: ignore
    except Exception:
        return False

    @server.routes.get("/arkflex/settings")
    async def read_settings(_request):
        return web.json_response({"ok": True, "keys": store.key_presence(), "defaults": store.read_defaults()})

    @server.routes.post("/arkflex/settings")
    async def write_settings(request):
        try:
            body = await request.json()
        except Exception:
            return web.json_response({"ok": False, "error": "expected a JSON body"}, status=400)
        if not isinstance(body, dict):
            return web.json_response({"ok": False, "error": "expected a JSON object"}, status=400)
        keys = {}
        for name in _SETTING_NAMES:
            value = body.get(name)
            if value is None:
                continue
            if not isinstance(value, str):
                return web.json_response({"ok": False, "error": f"{name} must be a string"}, status=400)
            keys[name] = value
        defaults = {}
        for name in _DEFAULT_NAMES:
            value = body.get(name)
            if value is None:
                continue
            if not isinstance(value, str):
                return web.json_response({"ok": False, "error": f"{name} must be a string"}, status=400)
            defaults[name] = value
        if not keys and not defaults:
            return web.json_response({"ok": False, "error": "nothing to save"}, status=400)
        try:
            saved = store.write_keys(
                keys.get("standard"),
                keys.get("agentPlan"),
                defaults.get("imageDefault"),
                defaults.get("videoDefault"),
            )
        except ValueError as error:
            return web.json_response({"ok": False, "error": str(error)}, status=400)
        except OSError as error:
            # A read-only checkout is a real state, not a crash.
            return web.json_response({"ok": False, "error": f"could not write config.json: {error}"}, status=500)
        return web.json_response({"ok": True, **saved})

    server._arkflex_routes = True
    return True


__all__ = ["register_routes"]
