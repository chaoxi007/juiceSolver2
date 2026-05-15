from __future__ import annotations

import json

from openai import AsyncOpenAI
from pydantic import BaseModel

from .base import LLMMessage, LLMProvider, LLMResponse


class OpenAIProvider(LLMProvider):
    def __init__(self, model: str, api_key: str, base_url: str = ""):
        self.model = model
        kwargs: dict = {"api_key": api_key}
        if base_url:
            kwargs["base_url"] = base_url
        self.client = AsyncOpenAI(**kwargs)

    async def complete(
        self,
        messages: list[LLMMessage],
        temperature: float = 0.7,
        max_tokens: int = 4096,
        json_mode: bool = False,
    ) -> LLMResponse:
        chat_messages = [{"role": m.role, "content": m.content} for m in messages]

        kwargs: dict = {
            "model": self.model,
            "messages": chat_messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}

        response = await self.client.chat.completions.create(**kwargs)
        choice = response.choices[0]

        return LLMResponse(
            content=choice.message.content or "",
            model=response.model,
            usage={
                "input_tokens": response.usage.prompt_tokens if response.usage else 0,
                "output_tokens": response.usage.completion_tokens if response.usage else 0,
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
