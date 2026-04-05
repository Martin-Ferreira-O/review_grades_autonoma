from __future__ import annotations

from typing import Any
from urllib.parse import urlsplit

import httpx

from uac_grades.infrastructure.config.settings import Settings
from uac_grades.infrastructure.persistence.session_store import SessionStateStore


class BannerHttpClient:
    _DEFAULT_TIMEOUT = 30.0
    _AUTH_PAGE_MARKERS = (
        'id="term"',
        'data-endpoint="/StudentSelfService/studentGrades/term"',
        'id="courseworkcontainer"',
        'id="studentgradescontainer"',
    )

    def __init__(
        self,
        settings: Settings,
        session_store: SessionStateStore,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
    ):
        self._settings = settings
        self._session_store = session_store
        self._transport = transport
        grades_url = urlsplit(settings.urls.grades)
        self._base_url = f"{grades_url.scheme}://{grades_url.netloc}"

    def create_client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            base_url=self._base_url,
            cookies=self._session_store.load_httpx_cookies(),
            follow_redirects=True,
            timeout=self._DEFAULT_TIMEOUT,
            transport=self._transport,
        )

    async def request(
        self,
        method: str,
        path_or_url: str,
        *,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> httpx.Response:
        if client is not None:
            response = await client.request(method, path_or_url, params=params, headers=headers)
            response.raise_for_status()
            return response

        async with self.create_client() as owned_client:
            response = await owned_client.request(method, path_or_url, params=params, headers=headers)
            response.raise_for_status()
            return response

    async def get_text(
        self,
        path_or_url: str,
        *,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> str:
        response = await self.request("GET", path_or_url, params=params, headers=headers, client=client)
        return response.text

    async def get_json(
        self,
        path_or_url: str,
        *,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> Any:
        response = await self.request("GET", path_or_url, params=params, headers=headers, client=client)
        return response.json()

    async def probe_grades_session(self) -> bool:
        if not self._session_store.exists():
            return False

        async with self.create_client() as client:
            response = await client.get(
                self._settings.urls.grades,
                headers={
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                },
            )

        return self._looks_like_authenticated_grades_page(response)

    def _looks_like_authenticated_grades_page(self, response: httpx.Response) -> bool:
        final_url = str(response.url).lower()
        if "microsoftonline.com" in final_url or "/ssomanager/" in final_url:
            return False

        text = response.text.lower()
        return any(marker in text for marker in self._AUTH_PAGE_MARKERS)
