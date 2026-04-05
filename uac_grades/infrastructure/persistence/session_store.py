from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx
from playwright.async_api import BrowserContext


class SessionStateStore:
    def __init__(self, storage_state_path: Path):
        self._storage_state_path = storage_state_path

    @property
    def path(self) -> Path:
        return self._storage_state_path

    def exists(self) -> bool:
        return self._storage_state_path.exists()

    def load(self) -> dict[str, Any]:
        if not self.exists():
            raise RuntimeError(f"No existe estado de sesion en {self._storage_state_path}")

        try:
            raw = self._storage_state_path.read_text(encoding="utf-8")
            payload = json.loads(raw)
        except json.JSONDecodeError as error:
            raise RuntimeError(f"El estado de sesion en {self._storage_state_path} no es JSON valido") from error

        if not isinstance(payload, dict):
            raise RuntimeError(f"El estado de sesion en {self._storage_state_path} no tiene el formato esperado")

        cookies = payload.get("cookies")
        if not isinstance(cookies, list):
            raise RuntimeError(f"El estado de sesion en {self._storage_state_path} no contiene una lista de cookies")

        origins = payload.get("origins", [])
        if origins is not None and not isinstance(origins, list):
            raise RuntimeError(f"El estado de sesion en {self._storage_state_path} tiene un campo origins invalido")

        return payload

    def load_httpx_cookies(self) -> httpx.Cookies:
        cookies = httpx.Cookies()

        for cookie in self.load()["cookies"]:
            if not isinstance(cookie, dict):
                raise RuntimeError(f"El estado de sesion en {self._storage_state_path} contiene cookies invalidas")

            name = str(cookie.get("name") or "").strip()
            if not name:
                raise RuntimeError(f"El estado de sesion en {self._storage_state_path} contiene una cookie sin nombre")

            cookies.set(
                name,
                str(cookie.get("value") or ""),
                domain=str(cookie.get("domain") or ""),
                path=str(cookie.get("path") or "/"),
            )

        return cookies

    async def save(self, context: BrowserContext) -> None:
        self._storage_state_path.parent.mkdir(parents=True, exist_ok=True)
        await context.storage_state(path=str(self._storage_state_path))
