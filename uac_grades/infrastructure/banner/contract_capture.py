from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from typing import Any
from urllib.parse import parse_qs, urlparse

from playwright.async_api import BrowserContext, Response

from uac_grades.infrastructure.persistence.debug_store import DebugArtifactStore


class BannerContractCapture:
    _TARGET_PATHS = {
        "/StudentSelfService/studentGrades/term",
        "/StudentSelfService/studentGrades/level",
        "/StudentSelfService/studentGrades/courses",
        "/StudentSelfService/programDetails/courseDetails",
        "/StudentSelfService/componentDetails/componentDetails",
        "/StudentSelfService/componentDetails/subComponentDetails",
    }
    _REQUEST_HEADER_ALLOWLIST = {"accept", "content-type", "origin", "referer", "x-requested-with"}
    _RESPONSE_HEADER_ALLOWLIST = {"content-type", "location"}

    def __init__(self, context: BrowserContext, debug_store: DebugArtifactStore):
        self._context = context
        self._debug_store = debug_store
        self._started = False
        self._active = False
        self._pending: set[asyncio.Task[None]] = set()
        self._captures: list[dict[str, Any]] = []
        self._errors: list[dict[str, str]] = []
        self._sequence = 0

    def start(self) -> None:
        if self._started:
            return

        self._context.on("response", self._on_response)
        self._started = True
        self._active = True

    async def stop(self) -> str | None:
        if not self._started:
            return None

        self._active = False
        self._started = False
        self._context.remove_listener("response", self._on_response)

        if self._pending:
            await asyncio.gather(*self._pending, return_exceptions=True)

        summary = {
            "captured_at": datetime.now(timezone.utc).isoformat(),
            "total_captures": len(self._captures),
            "captures": self._captures,
            "errors": self._errors,
        }
        path = self._debug_store.write_text(
            "banner_contract/summary.json",
            json.dumps(summary, indent=2, ensure_ascii=True),
        )
        return str(path)

    def _on_response(self, response: Response) -> None:
        if not self._active:
            return

        path = urlparse(response.url).path
        if path not in self._TARGET_PATHS:
            return

        self._sequence += 1
        task = asyncio.create_task(self._record_capture(self._sequence, response, path))
        self._pending.add(task)
        task.add_done_callback(self._pending.discard)

    async def _record_capture(self, sequence: int, response: Response, path: str) -> None:
        try:
            request = response.request
            request_headers = await request.all_headers()
            response_headers = await response.all_headers()
            capture = {
                "sequence": sequence,
                "captured_at": datetime.now(timezone.utc).isoformat(),
                "request": {
                    "method": request.method,
                    "url": request.url,
                    "path": path,
                    "query": self._normalize_query(request.url),
                    "headers": self._filter_headers(request_headers, self._REQUEST_HEADER_ALLOWLIST),
                    "post_data": self._parse_payload(request.post_data),
                },
                "response": {
                    "status": response.status,
                    "headers": self._filter_headers(response_headers, self._RESPONSE_HEADER_ALLOWLIST),
                    "body": await self._read_response_body(response),
                },
            }
            filename = f"banner_contract/{sequence:02d}_{self._path_key(path)}.json"
            self._debug_store.write_text(filename, json.dumps(capture, indent=2, ensure_ascii=True))
            self._captures.append(
                {
                    "sequence": sequence,
                    "path": path,
                    "file": filename,
                }
            )
        except Exception as error:
            self._errors.append({"sequence": str(sequence), "path": path, "error": str(error)})

    def _normalize_query(self, url: str) -> dict[str, str | list[str]]:
        query = parse_qs(urlparse(url).query, keep_blank_values=True)
        return {
            key: values[0] if len(values) == 1 else values
            for key, values in sorted(query.items())
        }

    def _filter_headers(self, headers: dict[str, str], allowlist: set[str]) -> dict[str, str]:
        return {
            key: value
            for key, value in sorted(headers.items())
            if key.lower() in allowlist
        }

    async def _read_response_body(self, response: Response) -> Any:
        text = await response.text()
        return self._parse_payload(text)

    def _parse_payload(self, payload: str | None) -> Any:
        if payload in (None, ""):
            return None

        try:
            return json.loads(payload)
        except json.JSONDecodeError:
            if len(payload) > 4000:
                return payload[:4000] + "...<truncated>"
            return payload

    def _path_key(self, path: str) -> str:
        parts = [part for part in path.split("/") if part]
        if len(parts) >= 2:
            return "_".join(parts[-2:])
        return parts[-1] if parts else "capture"
