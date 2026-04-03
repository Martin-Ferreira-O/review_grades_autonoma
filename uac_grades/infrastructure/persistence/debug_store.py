from __future__ import annotations

from pathlib import Path

from playwright.async_api import Page


class DebugArtifactStore:
    def __init__(self, base_dir: Path):
        self._base_dir = base_dir

    def _path(self, filename: str) -> Path:
        path = self._base_dir / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    async def save_screenshot(self, page: Page, filename: str) -> Path:
        path = self._path(filename)
        await page.screenshot(path=str(path))
        return path

    def write_text(self, filename: str, content: str) -> Path:
        path = self._path(filename)
        path.write_text(content, encoding="utf-8")
        return path

    async def save_page_state(self, page: Page, screenshot_name: str, html_name: str) -> tuple[Path, Path]:
        screenshot_path = await self.save_screenshot(page, screenshot_name)
        html_path = self.write_text(html_name, await page.content())
        return screenshot_path, html_path
