"""UseSkillHandler: bridges the Skill system into the Protocol/Action layer."""
from __future__ import annotations

import json

from ..actions.base import ActionHandler, ActionResult
from ..agent.protocol import Protocol
from ..skills.library import get_skill
from ..skills.runner import SkillRunner


class UseSkillHandler(ActionHandler):
    """Handle {"action": "use_skill", "params": {"skill": "...", ...}}."""

    def __init__(self, protocol: Protocol):
        # We need a reference to Protocol so SkillRunner can dispatch sub-actions
        self._protocol = protocol

    @property
    def name(self) -> str:
        return "use_skill"

    async def execute(self, params: dict, context: dict) -> ActionResult:
        skill_name = params.pop("skill", "")
        if not skill_name:
            return ActionResult(
                status="error",
                error="'skill' parameter is required. Provide the skill name.",
            )

        skill = get_skill(skill_name)
        if skill is None:
            # Provide available skills to help the LLM self-correct
            from ..skills.library import ALL_SKILLS

            available = sorted(ALL_SKILLS.keys())
            return ActionResult(
                status="error",
                error=f"Unknown skill '{skill_name}'. Available skills: {available[:20]}",
            )

        # Check auth requirement
        if skill.requires_auth:
            http = context.get("http")
            if http and not http.auth.has_token:
                return ActionResult(
                    status="error",
                    error=f"Skill '{skill_name}' requires authentication "
                          f"(level: {skill.requires_auth}). Please login first.",
                )

        runner = SkillRunner(self._protocol, context)
        result = await runner.execute(skill, params)

        return ActionResult(
            status="success" if result.success else "error",
            data=result.to_dict(),
            error="" if result.success else result.summary,
        )
