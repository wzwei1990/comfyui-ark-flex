"""The HTTP side: JSON calls, async video tasks, and file downloads.

Standard library only, so the package installs with no requirements and its
tests run on a bare interpreter.
"""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Callable

from .errors import ArkError, explain, task_failure

#: Generation tasks can legitimately take minutes; this bounds the poll loop.
DEFAULT_TASK_TIMEOUT = 1_800.0
DEFAULT_POLL_SECONDS = 2.0


def build_multipart(
    fields: dict[str, str],
    images: list[tuple[str, bytes, str]],
    boundary: str,
) -> bytes:
    """A `multipart/form-data` body: text fields first, then `image[]` files.

    Split out so the wire format can be tested without a server.
    """
    body = bytearray()
    for name, value in fields.items():
        body += f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n'.encode("utf-8")
    for filename, blob, mime in images:
        body += (
            f'--{boundary}\r\nContent-Disposition: form-data; name="image[]"; filename="{filename}"\r\n'
            f"Content-Type: {mime}\r\n\r\n"
        ).encode("utf-8")
        body += blob + b"\r\n"
    body += f"--{boundary}--\r\n".encode("utf-8")
    return bytes(body)


class ArkClient:
    """One profile's worth of access to Ark."""

    def __init__(self, base_url: str, api_key: str, *, timeout: float = 120.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout

    # ── transport ────────────────────────────────────────────────────────

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def _request(self, method: str, path: str, payload: dict | None, *, timeout: float | None = None) -> dict:
        url = f"{self.base_url}{path}"
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8") if payload is not None else None
        request = urllib.request.Request(url, data=data, headers=self._headers(), method=method)
        return self._send(request, url, timeout)

    def _send(self, request: urllib.request.Request, url: str, timeout: float | None) -> dict:
        try:
            with urllib.request.urlopen(request, timeout=timeout or self.timeout) as response:
                text = response.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as error:
            body = error.read().decode("utf-8", "replace")
            raise ArkError(explain(error.code, body, self.base_url)) from None
        except urllib.error.URLError as error:
            raise ArkError(f"无法连接 {self.base_url}：{error.reason}") from None
        if not text.strip():
            return {}
        try:
            value = json.loads(text)
        except ValueError:
            raise ArkError(f"接口返回的不是 JSON（{url}）：{text[:200]}") from None
        if isinstance(value, dict) and isinstance(value.get("error"), dict):
            # A 200 with an embedded error still means the call failed.
            raise ArkError(f"接口返回错误：{json.dumps(value['error'], ensure_ascii=False)[:300]}")
        return value if isinstance(value, dict) else {"data": value}

    def images_edits(
        self,
        fields: dict[str, str],
        images: list[tuple[str, bytes, str]],
        *,
        timeout: float = 300.0,
    ) -> dict:
        """`multipart/form-data` upload to `/images/edits` (strict OpenAI shape).

        Relays that accept data URLs in a JSON body should use `refs_mode: json`
        instead; this path exists for the real OpenAI edits endpoint.
        """
        boundary = f"----arkflex{os.urandom(8).hex()}"
        body = build_multipart(fields, images, boundary)

        headers = {
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "Accept": "application/json",
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        url = f"{self.base_url}/images/edits"
        request = urllib.request.Request(url, data=body, headers=headers, method="POST")
        return self._send(request, url, timeout)

    def post(self, path: str, payload: dict, *, timeout: float | None = None) -> dict:
        return self._request("POST", path, payload, timeout=timeout)

    def get(self, path: str, *, timeout: float | None = None) -> dict:
        return self._request("GET", path, None, timeout=timeout)

    # ── media generation ─────────────────────────────────────────────────

    def images(self, payload: dict) -> dict:
        """Synchronous image generation."""
        return self.post("/images/generations", payload, timeout=300.0)

    def submit_video(self, payload: dict) -> str:
        """Create one async video task; returns its id."""
        result = self.post("/contents/generations/tasks", payload)
        task_id = result.get("id") or result.get("task_id")
        if not isinstance(task_id, str) or not task_id:
            raise ArkError(f"创建视频任务后没有拿到任务 id：{json.dumps(result, ensure_ascii=False)[:300]}")
        return task_id

    def wait_video(
        self,
        task_id: str,
        *,
        poll_seconds: float = DEFAULT_POLL_SECONDS,
        timeout: float = DEFAULT_TASK_TIMEOUT,
        on_tick: Callable[[dict], None] | None = None,
    ) -> dict:
        """Poll a task until it succeeds, fails, or the wait runs out."""
        deadline = time.monotonic() + max(1.0, timeout)
        last: dict = {}
        while time.monotonic() < deadline:
            last = self.get(f"/contents/generations/tasks/{task_id}")
            status = str(last.get("status") or "").lower()
            if on_tick is not None:
                on_tick(last)
            if status in ("succeeded", "success", "completed", "done"):
                return last
            if status in ("failed", "error", "cancelled", "canceled"):
                raise ArkError(task_failure(last))
            time.sleep(max(0.2, poll_seconds))
        raise ArkError(
            f"视频任务等待超时（{int(timeout)} 秒，任务 {task_id}，最后状态 {last.get('status') or '未知'}）。"
            "任务可能仍在方舟侧运行，可稍后用任务 id 重新查询。"
        )

    # ── files ────────────────────────────────────────────────────────────

    def download(self, url: str, dest_dir: Path, *, filename: str | None = None, timeout: float = 600.0) -> Path:
        """Stream one produced file into `dest_dir` and return its path."""
        dest_dir.mkdir(parents=True, exist_ok=True)
        name = filename or os.path.basename(url.split("?")[0]) or "ark-output.bin"
        path = dest_dir / name
        stem, suffix = path.stem, path.suffix
        index = 1
        while path.exists():
            path = dest_dir / f"{stem}-{index}{suffix}"
            index += 1
        request = urllib.request.Request(url, headers={"Accept": "*/*"}, method="GET")
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response, path.open("wb") as handle:
                while True:
                    chunk = response.read(1 << 20)
                    if not chunk:
                        break
                    handle.write(chunk)
        except urllib.error.HTTPError as error:
            raise ArkError(f"下载生成结果失败（HTTP {error.code}）：{url}") from None
        except urllib.error.URLError as error:
            raise ArkError(f"下载生成结果失败：{error.reason}（{url}）") from None
        return path
