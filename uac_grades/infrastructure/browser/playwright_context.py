from __future__ import annotations

from playwright.async_api import BrowserContext, Page, async_playwright

from uac_grades.infrastructure.config.settings import Settings


class PlaywrightBrowserSession:
    def __init__(self, settings: Settings):
        self._settings = settings
        self._playwright = None
        self._context: BrowserContext | None = None
        self._page: Page | None = None

    @property
    def context(self) -> BrowserContext:
        if self._context is None:
            raise RuntimeError("El contexto de Playwright no está inicializado")
        return self._context

    @property
    def page(self) -> Page:
        if self._page is None:
            raise RuntimeError("La página de Playwright no está inicializada")
        return self._page

    async def __aenter__(self) -> "PlaywrightBrowserSession":
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.close()

    async def start(self) -> None:
        self._settings.storage.auth_dir.mkdir(parents=True, exist_ok=True)
        self._playwright = await async_playwright().start()
        self._context = await self._playwright.chromium.launch_persistent_context(
            str(self._settings.storage.user_data_dir),
            headless=self._settings.browser.headless,
            slow_mo=self._settings.browser.slow_mo,
            viewport={
                "width": self._settings.browser.viewport_width,
                "height": self._settings.browser.viewport_height,
            },
            locale=self._settings.browser.locale,
            timezone_id=self._settings.browser.timezone_id,
        )
        self._page = self._context.pages[0] if self._context.pages else await self._context.new_page()

    async def close(self) -> None:
        if self._context is not None:
            await self._context.close()
            self._context = None
            self._page = None

        if self._playwright is not None:
            await self._playwright.stop()
            self._playwright = None
