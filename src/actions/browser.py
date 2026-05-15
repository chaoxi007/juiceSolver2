"""ActionHandler for browser-based navigation (Playwright)."""
from __future__ import annotations

from ..browser.session import BrowserSession
from .base import ActionHandler, ActionResult


class BrowserNavigateHandler(ActionHandler):
    @property
    def name(self) -> str:
        return "browser_navigate"

    async def execute(self, params: dict, context: dict) -> ActionResult:
        session: BrowserSession | None = context.get("browser")
        if session is None:
            return ActionResult(status="error", error="Browser session not available")

        path = params.get("path", "")
        if not path:
            return ActionResult(status="error", error="'path' is required")

        wait_until = params.get("wait_until", "networkidle")
        wait_for_selector = params.get("wait_for_selector")
        extract_selector = params.get("extract_selector")

        try:
            result = await session.navigate(
                path=path,
                wait_until=wait_until,
                wait_for_selector=wait_for_selector,
                extract_selector=extract_selector,
            )
            return ActionResult(status="success", data=result)
        except Exception as e:
            return ActionResult(status="error", error=f"{type(e).__name__}: {e}")
