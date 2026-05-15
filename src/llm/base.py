from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel


@dataclass
class LLMMessage:
    role: str  # "system", "user", "assistant"
    content: str


@dataclass
class LLMResponse:
    content: str
    model: str
    usage: dict[str, int] = field(default_factory=dict)
    raw: Any = None


class LLMProvider(ABC):
    @abstractmethod
    async def complete(
        self,
        messages: list[LLMMessage],
        temperature: float = 0.7,
        max_tokens: int = 4096,
        json_mode: bool = False,
    ) -> LLMResponse: ...

    @abstractmethod
    async def complete_structured(
        self,
        messages: list[LLMMessage],
        schema: type[BaseModel],
        temperature: float = 0.3,
    ) -> tuple[LLMResponse, BaseModel]: ...
