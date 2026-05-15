from __future__ import annotations

import json

from anthropic import AsyncAnthropic
from pydantic import BaseModel

from .base import LLMMessage, LLMProvider, LLMResponse


class ClaudeProvider(LLMProvider):
    def __init__(self, model: str, api_key: str, base_url: str = ""):
        self.model = model
        kwargs: dict = {"api_key": api_key, "timeout": 120.0}
        if base_url:
            kwargs["base_url"] = base_url
        self.client = AsyncAnthropic(**kwargs)

    async def complete(
        self,
        messages: list[LLMMessage],
        temperature: float = 0.7,
        max_tokens: int = 4096,
        json_mode: bool = False,
    ) -> LLMResponse:
        system_msg = None
        chat_messages = []
        for msg in messages:
            if msg.role == "system":
                system_msg = msg.content
            else:
                chat_messages.append({"role": msg.role, "content": msg.content})

        kwargs: dict = {
            "model": self.model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": chat_messages,
        }
        if system_msg:
            kwargs["system"] = system_msg

        response = await self.client.messages.create(**kwargs)
        content = response.content[0].text

        return LLMResponse(
            content=content,
            model=response.model,
            usage={
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
            },
            raw=response,
        )

    async def complete_structured(
        self,
        messages: list[LLMMessage],
        schema: type[BaseModel],
        temperature: float = 0.3,
    ) -> tuple[LLMResponse, BaseModel]:
        schema_json = json.dumps(schema.model_json_schema(), indent=2)
        augmented = list(messages)
        augmented.append(LLMMessage(
            role="user",
            content=f"Respond with valid JSON matching this schema:\n{schema_json}\nNo other text.",
        ))

        resp = await self.complete(augmented, temperature=temperature, json_mode=True)
        parsed = schema.model_validate_json(resp.content)
        return resp, parsed
