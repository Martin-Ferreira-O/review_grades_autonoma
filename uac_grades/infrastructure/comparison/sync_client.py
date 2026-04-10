from __future__ import annotations

import httpx


class ComparisonSyncClient:
    def __init__(self, *, base_url: str, timeout: float = 20.0):
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout

    async def sync(self, payload: dict) -> dict:
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.post(f"{self._base_url}/api/comparison/sync", json=payload)
            response.raise_for_status()
            return response.json()
