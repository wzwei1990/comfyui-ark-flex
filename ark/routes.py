"""The two endpoints the Settings dialog talks to.

Keys are typed in ComfyUI's Settings dialog, posted here, and written into this
pack's own `config.json`; the dialog then shows a marker instead of the secret.
That keeps the key inside the node folder, so removing the folder removes the
key too.
"""
from __future__ import annotations

from . import store

#: POST body field -> store.write_settings keyword.
_FIELDS = {
    "arkStandard": "ark_standard",
    "arkPlan": "ark_plan",
    "arkImageModel": "ark_image_model",
    "arkVideoModel": "ark_video_model",
    "openaiBaseUrl": "openai_base_url",
    "openaiApiKey": "openai_api_key",
    "openaiRefsMode": "openai_refs_mode",
    "openaiModel": "openai_model",
    "imageDefault": "image_default",
    "videoDefault": "video_default",
}


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
        return web.json_response({"ok": True, **store.presence()})

    @server.routes.post("/arkflex/settings")
    async def write_settings(request):
        try:
            body = await request.json()
        except Exception:
            return web.json_response({"ok": False, "error": "expected a JSON body"}, status=400)
        if not isinstance(body, dict):
            return web.json_response({"ok": False, "error": "expected a JSON object"}, status=400)
        values = {}
        for field, keyword in _FIELDS.items():
            value = body.get(field)
            if value is None:
                continue
            if not isinstance(value, str):
                return web.json_response({"ok": False, "error": f"{field} must be a string"}, status=400)
            values[keyword] = value
        if not values:
            return web.json_response({"ok": False, "error": "nothing to save"}, status=400)
        try:
            saved = store.write_settings(**values)
        except ValueError as error:
            return web.json_response({"ok": False, "error": str(error)}, status=400)
        except OSError as error:
            # A read-only checkout is a real state, not a crash.
            return web.json_response({"ok": False, "error": f"could not write config.json: {error}"}, status=500)
        return web.json_response({"ok": True, **saved})

    server._arkflex_routes = True
    return True


__all__ = ["register_routes"]
