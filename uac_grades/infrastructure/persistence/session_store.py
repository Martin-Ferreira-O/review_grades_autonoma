from __future__ import annotations

from pathlib import Path

from playwright.async_api import BrowserContext


class SessionStateStore:
    def __init__(self, storage_state_path: Path):
        self._storage_state_path = storage_state_path

    @property
    def path(self) -> Path:
        return self._storage_state_path

    async def save(self, context: BrowserContext) -> None:
        self._storage_state_path.parent.mkdir(parents=True, exist_ok=True)
        await context.storage_state(path=str(self._storage_state_path))
