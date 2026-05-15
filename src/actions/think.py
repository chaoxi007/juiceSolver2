from __future__ import annotations

from .base import ActionHandler, ActionResult


class ThinkHandler(ActionHandler):
    @property
    def name(self) -> str:
        return "think"

    async def execute(self, params: dict, context: dict) -> ActionResult:
        return ActionResult(status="success", data={"acknowledged": True})
