"""SkillRunner: executes multi-step Skill sequences with template resolution."""
from __future__ import annotations

import copy
import json
import re
from typing import Any

from ..actions.base import ActionRequest, ActionResult
from ..agent.protocol import Protocol
from ..utils.logging import get_logger
from .base import Skill, SkillResult, SkillStep, StepOutcome

logger = get_logger(__name__)


class SkillRunner:
    """Execute a Skill's step sequence, handling variable substitution and flow control."""

    def __init__(self, protocol: Protocol, context: dict):
        self.protocol = protocol
        self.context = context

    async def execute(self, skill: Skill, params: dict) -> SkillResult:
        """Run all steps of a skill sequentially."""
        variables: dict[str, Any] = dict(params)
        outcomes: list[StepOutcome] = []

        # Build effective steps list (auto-append check_solved if needed)
        steps = list(skill.steps)
        if skill.post_check and not any(s.action == "check_solved" for s in steps):
            steps.append(SkillStep(action="check_solved", params={}))

        total = len(steps)
        solved = False

        for i, step in enumerate(steps):
            # 1. Resolve template variables in params
            resolved_params = self._resolve(step.params, variables)

            logger.info(
                f"    Skill [{skill.name}] step {i + 1}/{total}: "
                f"{step.action} {_preview(resolved_params)}"
            )

            # 2. Dispatch through Protocol (reuses all existing ActionHandlers)
            request = ActionRequest(action=step.action, params=resolved_params)
            result = await self.protocol.dispatch(request, self.context)

            outcome = StepOutcome(
                step_index=i,
                action=step.action,
                status=result.status,
                data=result.data,
                error=result.error,
            )
            outcomes.append(outcome)

            # 3. Check expected status code
            if step.expect_status is not None and result.status == "success":
                actual = result.data.get("status_code")
                if actual != step.expect_status:
                    logger.warning(
                        f"    Step {i + 1}: expected {step.expect_status}, got {actual}"
                    )
                    if step.on_fail == "abort":
                        return SkillResult(
                            skill_name=skill.name,
                            success=False,
                            solved=False,
                            steps_executed=i + 1,
                            steps_total=total,
                            step_outcomes=outcomes,
                            summary=f"Aborted at step {i + 1}: expected status {step.expect_status}, got {actual}",
                        )

            # 4. Extract variables for downstream steps
            if step.extract and result.status == "success":
                for var_name, key_path in step.extract.items():
                    extracted = self._extract(result.data, key_path)
                    if extracted is not None:
                        variables[var_name] = extracted

            # 5. Check if challenge was solved
            if step.action == "check_solved" and result.data.get("solved"):
                solved = True
                return SkillResult(
                    skill_name=skill.name,
                    success=True,
                    solved=True,
                    steps_executed=i + 1,
                    steps_total=total,
                    step_outcomes=outcomes,
                    summary=f"Challenge SOLVED after step {i + 1}/{total}!",
                )

            # 6. Handle errors
            if result.status == "error" and step.on_fail == "abort":
                return SkillResult(
                    skill_name=skill.name,
                    success=False,
                    solved=False,
                    steps_executed=i + 1,
                    steps_total=total,
                    step_outcomes=outcomes,
                    summary=f"Error at step {i + 1}: {result.error}",
                )

        # All steps done, not solved
        return SkillResult(
            skill_name=skill.name,
            success=True,
            solved=False,
            steps_executed=total,
            steps_total=total,
            step_outcomes=outcomes,
            summary=f"All {total} steps completed but challenge not solved yet.",
        )

    # ── Template resolution ──────────────────────────────────────────

    def _resolve(self, params: dict, variables: dict) -> dict:
        """Deep-copy params and replace all {variable} placeholders."""
        resolved = copy.deepcopy(params)
        return self._resolve_recursive(resolved, variables)

    def _resolve_recursive(self, obj: Any, variables: dict) -> Any:
        if isinstance(obj, str):
            # Full replacement: if the entire string is "{var}", replace with the actual value
            # (preserves type, e.g. dict stays dict)
            match = re.fullmatch(r"\{(\w+)\}", obj)
            if match and match.group(1) in variables:
                return variables[match.group(1)]
            # Partial replacement: "prefix {var} suffix" -> string interpolation
            def replacer(m: re.Match) -> str:
                key = m.group(1)
                val = variables.get(key)
                if val is None:
                    return m.group(0)  # keep placeholder if not found
                return json.dumps(val) if isinstance(val, (dict, list)) else str(val)
            return re.sub(r"\{(\w+)\}", replacer, obj)
        elif isinstance(obj, dict):
            return {k: self._resolve_recursive(v, variables) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._resolve_recursive(item, variables) for item in obj]
        return obj

    # ── Value extraction ─────────────────────────────────────────────

    @staticmethod
    def _extract(data: dict, key_path: str) -> Any:
        """Simple dot-notation extraction from nested dict. E.g. 'authentication.token'"""
        # Strip leading "$." for JSONPath-like syntax
        path = key_path.lstrip("$.")
        current: Any = data
        for part in path.split("."):
            if isinstance(current, dict):
                current = current.get(part)
            else:
                return None
        return current


def _preview(params: dict) -> str:
    """Short preview of params for logging."""
    s = json.dumps(params, ensure_ascii=False)
    return s[:80] + "..." if len(s) > 80 else s
