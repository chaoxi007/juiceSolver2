from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ActionRequest:
    action: str
    params: dict = field(default_factory=dict)


@dataclass
class ActionResult:
    status: str  # "success" or "error"
    data: dict = field(default_factory=dict)
    error: str = ""

    def to_dict(self) -> dict:
        d: dict[str, Any] = {"status": self.status, "data": self.data}
        if self.error:
            d["error"] = self.error
        return d


class ActionHandler(ABC):
    @property
    @abstractmethod
    def name(self) -> str: ...

    @abstractmethod
    async def execute(self, params: dict, context: dict) -> ActionResult: ...
