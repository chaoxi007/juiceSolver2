"""Lazy-initialized Playwright browser session, shared across an agent run."""
from __future__ import annotations

from typing import Any

from ..utils.logging import get_logger

logger = get_logger(__name__)


class BrowserSession:
    """Manages a single browser context reused for the entire agent session."""

    def __init__(self, base_url: str, headless: bool = True):
        self._base_url = base_url.rstrip("/")
        self._headless = headless
        self._playwright: Any = None
        self._browser: Any = None
        self._context: Any = None
        self._page: Any = None

    @property
    def ready(self) -> bool:
        return self._page is not None

    async def ensure_ready(self):
        """Lazy-start browser on first use."""
        if self._page is not None:
            return self._page

        from playwright.async_api import async_playwright

        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(headless=self._headless)
        self._context = await self._browser.new_context(base_url=self._base_url)
        self._page = await self._context.new_page()
        logger.info(f"Browser session started (base_url={self._base_url})")
        return self._page

    async def navigate(
        self,
        path: str,
        wait_until: str = "networkidle",
        wait_for_selector: str | None = None,
        extract_selector: str | None = None,
    ) -> dict:
        """Navigate to path and optionally extract content."""
        page = await self.ensure_ready()
        url = path if path.startswith("http") else f"{self._base_url}/{path.lstrip('/')}"

        resp = await page.goto(url, wait_until=wait_until, timeout=15000)

        if wait_for_selector:
            await page.wait_for_selector(wait_for_selector, timeout=10000)

        result: dict = {
            "url": page.url,
            "status": resp.status if resp else None,
            "title": await page.title(),
        }

        if extract_selector:
            elements = await page.query_selector_all(extract_selector)
            texts = []
            for el in elements[:10]:
                texts.append(await el.inner_text())
            result["extracted"] = texts
        else:
            result["body_preview"] = (await page.content())[:2000]

        return result

    async def close(self):
        if self._browser:
            await self._browser.close()
            self._browser = None
        if self._playwright:
            await self._playwright.stop()
            self._playwright = None
        self._page = None
        self._context = None
