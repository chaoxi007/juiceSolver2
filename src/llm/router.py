from __future__ import annotations

from .base import LLMMessage, LLMProvider, LLMResponse
from .claude_provider import ClaudeProvider
from .openai_provider import OpenAIProvider
from ..utils.config import Config

from pydantic import BaseModel


class LLMRouter:
    def __init__(self, config: Config):
        self._providers: dict[str, LLMProvider] = {}
        self._routing = config.llm.routing
        self._default = config.llm.default_provider
        self._init_providers(config)

    def _init_providers(self, config: Config) -> None:
        for name, pconf in config.llm.providers.items():
            if not pconf.api_key:
                continue
            if name == "claude":
                self._providers[name] = ClaudeProvider(
                    model=pconf.model, api_key=pconf.api_key, base_url=pconf.base_url
                )
            elif name == "openai":
                self._providers[name] = OpenAIProvider(
                    model=pconf.model, api_key=pconf.api_key, base_url=pconf.base_url
                )

        if not self._providers:
            raise ValueError("No valid LLM provider configured. Set api_key in config.yaml.")

    def _get_provider(self, task_type: str) -> LLMProvider:
        provider_name = self._routing.get(task_type, self._default)
        if provider_name not in self._providers:
            provider_name = self._default
        return self._providers[provider_name]

    async def complete(
        self,
        messages: list[LLMMessage],
        task_type: str = "general",
        temperature: float = 0.7,
        max_tokens: int = 4096,
        json_mode: bool = False,
    ) -> LLMResponse:
        provider = self._get_provider(task_type)
        return await provider.complete(
            messages, temperature=temperature, max_tokens=max_tokens, json_mode=json_mode
        )

    async def complete_structured(
        self,
        messages: list[LLMMessage],
        schema: type[BaseModel],
        task_type: str = "general",
        temperature: float = 0.3,
    ) -> tuple[LLMResponse, BaseModel]:
        provider = self._get_provider(task_type)
        return await provider.complete_structured(messages, schema, temperature=temperature)
