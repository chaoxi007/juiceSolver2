from __future__ import annotations

from .base import ActionHandler, ActionResult


class GiveUpHandler(ActionHandler):
    @property
    def name(self) -> str:
        return "give_up"

    async def execute(self, params: dict, context: dict) -> ActionResult:
        reason = params.get("reason", "No reason given")
        return ActionResult(status="success", data={"skipped": True, "reason": reason})
