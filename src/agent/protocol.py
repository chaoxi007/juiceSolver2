from __future__ import annotations

import json
from typing import Any

from ..actions.base import ActionHandler, ActionRequest, ActionResult


class Protocol:
    def __init__(self) -> None:
        self._handlers: dict[str, ActionHandler] = {}

    def register(self, handler: ActionHandler) -> None:
        self._handlers[handler.name] = handler

    @property
    def action_names(self) -> list[str]:
        return list(self._handlers.keys())

    def parse(self, raw: str) -> ActionRequest | None:
        try:
            obj = json.loads(raw.strip())
        except json.JSONDecodeError:
            extracted = self._extract_json(raw)
            if extracted is None:
                return None
            obj = extracted

        if not isinstance(obj, dict) or "action" not in obj:
            return None

        action = obj["action"]
        params = obj.get("params", {})
        if not isinstance(params, dict):
            params = {}

        return ActionRequest(action=action, params=params)

    async def dispatch(self, request: ActionRequest, context: dict) -> ActionResult:
        handler = self._handlers.get(request.action)
        if handler is None:
            return ActionResult(
                status="error",
                error=f"Unknown action '{request.action}'. Available: {self.action_names}",
            )
        return await handler.execute(request.params, context)

    def format_result(self, result: ActionResult) -> str:
        return json.dumps(result.to_dict(), ensure_ascii=False)

    def _extract_json(self, text: str) -> dict[str, Any] | None:
        start = text.find("{")
        if start == -1:
            return None
        depth = 0
        for i in range(start, len(text)):
            if text[i] == "{":
                depth += 1
            elif text[i] == "}":
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(text[start : i + 1])
                    except json.JSONDecodeError:
                        return None
        return None
