from __future__ import annotations

from ..discovery.challenges import ChallengeDiscovery
from .base import ActionHandler, ActionResult


class CheckSolvedHandler(ActionHandler):
    @property
    def name(self) -> str:
        return "check_solved"

    async def execute(self, params: dict, context: dict) -> ActionResult:
        discovery: ChallengeDiscovery = context["discovery"]
        challenge_id: int = context["challenge_id"]

        solved = await discovery.check_solved(challenge_id)
        return ActionResult(status="success", data={"solved": solved})
