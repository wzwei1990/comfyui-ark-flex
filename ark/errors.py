"""Turning HTTP failures into something a user can act on.

The failure this pack exists to prevent is the silent 403: a standard key
against the Agent Plan URL (or the reverse) looks like a permissions bug but is
really one field in one profile.
"""
from __future__ import annotations


class ArkError(RuntimeError):
    """A failed Ark call, already explained."""


def _snippet(body: object, limit: int = 300) -> str:
    text = body if isinstance(body, str) else repr(body)
    text = " ".join(text.split())
    return text if len(text) <= limit else text[:limit] + "…"


def explain(status: int, body: object, base_url: str) -> str:
    """A sentence that names the likely cause, then the server's own words."""
    where = "/api/plan/v3" if "/api/plan/" in base_url else base_url
    if status in (401, 403):
        surface = "Agent Plan" if "/api/plan/" in base_url else "标准 API"
        other = "标准 API（/api/v3）" if surface == "Agent Plan" else "Agent Plan（/api/plan/v3）"
        return (
            f"鉴权失败（HTTP {status}）：当前 profile 指向 {surface} 的 {where}。"
            f"方舟两种入口的 Key 互不通用 —— 这个 Key 很可能属于{other}。"
            f"请检查节点上的 profile / base_url 是否与 Key 匹配。服务器返回：{_snippet(body)}"
        )
    if status == 404:
        return f"接口不存在（HTTP 404）：{where} 可能不是有效的方舟入口，或模型 / 任务 id 写错了。服务器返回：{_snippet(body)}"
    if status == 429:
        return f"触发限流（HTTP 429）：稍后重试，或降低并发。服务器返回：{_snippet(body)}"
    if status >= 500:
        return f"方舟服务端错误（HTTP {status}）：通常可重试。服务器返回：{_snippet(body)}"
    return f"请求失败（HTTP {status}）指向 {where}。服务器返回：{_snippet(body)}"


def task_failure(task: dict) -> str:
    """The reason a generation task failed, in the clearest words available."""
    error = task.get("error") if isinstance(task, dict) else None
    if isinstance(error, dict):
        code = error.get("code") or error.get("type") or ""
        message = error.get("message") or _snippet(error)
        return f"生成任务失败{f'（{code}）' if code else ''}：{message}"
    if isinstance(error, str) and error.strip():
        return f"生成任务失败：{error.strip()}"
    status = task.get("status") if isinstance(task, dict) else None
    return f"生成任务失败：状态为 {status}，且没有错误详情。响应：{_snippet(task)}"
