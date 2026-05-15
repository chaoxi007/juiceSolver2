from __future__ import annotations

from ..memory.store import MemoryStore
from .base import ActionHandler, ActionResult


class ReadMemoryHandler(ActionHandler):
    @property
    def name(self) -> str:
        return "read_memory"

    async def execute(self, params: dict, context: dict) -> ActionResult:
        memory: MemoryStore = context["memory"]
        category = params.get("category", "")
        key = params.get("key")

        if not category:
            return ActionResult(status="error", error="'category' is required")

        entries = memory.read(category, key)
        return ActionResult(status="success", data={"entries": entries})


class WriteMemoryHandler(ActionHandler):
    @property
    def name(self) -> str:
        return "write_memory"

    async def execute(self, params: dict, context: dict) -> ActionResult:
        memory: MemoryStore = context["memory"]
        category = params.get("category", "")
        key = params.get("key", "")
        value = params.get("value")

        if not category or not key:
            return ActionResult(status="error", error="'category' and 'key' are required")
        if value is None:
            return ActionResult(status="error", error="'value' is required")

        memory.write(category, key, value)
        return ActionResult(status="success", data={
            "written": True,
            "category": category,
            "key": key,
        })
