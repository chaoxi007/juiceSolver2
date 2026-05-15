"""Skill data structures: Skill, SkillStep, SkillResult."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class SkillStep:
    """A single step within a Skill's execution sequence."""

    action: str  # "http_request" | "login" | "check_solved" | ...
    params: dict = field(default_factory=dict)  # supports {template} variables
    expect_status: int | None = None  # expected HTTP status code
    extract: dict[str, str] | None = None  # variable_name -> JSONPath-like key
    on_fail: str = "continue"  # "continue" | "abort"


@dataclass
class Skill:
    """A reusable, pre-orchestrated multi-step attack technique."""

    name: str  # e.g. "sqli_login_bypass"
    description: str  # human-readable description for LLM
    category: str  # "injection" | "forced_browsing" | "idor" | ...
    steps: list[SkillStep]
    params_schema: dict[str, str] = field(default_factory=dict)  # param_name -> description
    post_check: bool = True  # auto-append check_solved if not already present
    requires_auth: str | None = None  # None | "user" | "admin"


@dataclass
class StepOutcome:
    """Result of a single step execution."""

    step_index: int
    action: str
    status: str  # "success" | "error"
    data: dict = field(default_factory=dict)
    error: str = ""


@dataclass
class SkillResult:
    """Aggregated result of a full Skill execution."""

    skill_name: str
    success: bool
    solved: bool
    steps_executed: int
    steps_total: int
    step_outcomes: list[StepOutcome] = field(default_factory=list)
    summary: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "skill": self.skill_name,
            "success": self.success,
            "solved": self.solved,
            "steps_executed": self.steps_executed,
            "steps_total": self.steps_total,
            "summary": self.summary,
            "step_details": [
                {
                    "step": o.step_index,
                    "action": o.action,
                    "status": o.status,
                    "data_preview": str(o.data)[:200] if o.data else "",
                    "error": o.error,
                }
                for o in self.step_outcomes
            ],
        }
