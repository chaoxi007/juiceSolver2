from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..utils.logging import get_logger

logger = get_logger(__name__)

CATEGORIES = ("credentials", "endpoints", "attack_results", "target_profile")


class MemoryStore:
    def __init__(self, path: Path | str = "data/memory.json"):
        self.path = Path(path)
        self._data: dict[str, dict] = {cat: {} for cat in CATEGORIES}
        self._load()

    def _load(self) -> None:
        if self.path.exists():
            try:
                raw = json.loads(self.path.read_text(encoding="utf-8"))
                for cat in CATEGORIES:
                    self._data[cat] = raw.get(cat, {})
                logger.info(f"Memory loaded: {sum(len(v) for v in self._data.values())} entries")
            except (json.JSONDecodeError, OSError) as e:
                logger.warning(f"Failed to load memory: {e}")

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self._data, indent=2, ensure_ascii=False), encoding="utf-8")

    def read(self, category: str, key: str | None = None) -> dict:
        if category not in CATEGORIES:
            return {}
        store = self._data[category]
        if key is not None:
            val = store.get(key)
            return {key: val} if val is not None else {}
        return dict(store)

    def write(self, category: str, key: str, value: Any) -> None:
        if category not in CATEGORIES:
            return
        if isinstance(value, dict) and key in self._data[category]:
            self._data[category][key].update(value)
        else:
            self._data[category][key] = value
        self.save()

    def get_relevant(self, challenge_category: str, challenge_key: str) -> dict:
        """Return memory entries relevant to a challenge."""
        result: dict[str, Any] = {}

        result["credentials"] = self._data["credentials"]
        result["target_profile"] = self._data["target_profile"]

        endpoints = self._data["endpoints"]
        result["endpoints"] = endpoints

        attack_results = self._data["attack_results"]
        relevant_attacks = {}
        for k, v in attack_results.items():
            if k == challenge_key:
                relevant_attacks[k] = v
            elif isinstance(v, dict) and v.get("category") == challenge_category:
                relevant_attacks[k] = v
            elif isinstance(v, dict) and challenge_key in v.get("related_challenges", []):
                relevant_attacks[k] = v
        result["attack_results"] = relevant_attacks

        return result
