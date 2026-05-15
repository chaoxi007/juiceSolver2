"""World Model: structured knowledge about the target, maintained across challenges."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..utils.logging import get_logger

logger = get_logger(__name__)


class WorldModel:
    """Persistent structured knowledge about the target application."""

    def __init__(self, path: Path | str = "data/world_model.json"):
        self.path = Path(path)
        self._data: dict[str, Any] = {
            "server": {},
            "routes": {},
            "users": [],
            "file_system": {},
            "attack_surface": {},
            "insights": [],
        }
        self._load()

    def _load(self) -> None:
        if self.path.exists():
            try:
                self._data = json.loads(self.path.read_text(encoding="utf-8"))
                logger.info(f"World model loaded: {len(self._data.get('routes', {}))} routes, {len(self._data.get('users', []))} users")
            except (json.JSONDecodeError, OSError) as e:
                logger.warning(f"Failed to load world model: {e}")

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(self._data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def merge_update(self, update: dict) -> None:
        """Merge an LLM-extracted update into the world model."""
        for key in ("server", "attack_surface", "file_system"):
            if key in update and isinstance(update[key], dict):
                self._data.setdefault(key, {}).update(update[key])

        if "routes" in update and isinstance(update["routes"], dict):
            for route, info in update["routes"].items():
                existing = self._data.setdefault("routes", {}).get(route, {})
                if isinstance(info, dict) and isinstance(existing, dict):
                    existing.update(info)
                    self._data["routes"][route] = existing
                else:
                    self._data["routes"][route] = info

        if "users" in update and isinstance(update["users"], list):
            existing_emails = {u.get("email") for u in self._data.get("users", [])}
            for user in update["users"]:
                if isinstance(user, dict) and user.get("email") not in existing_emails:
                    self._data.setdefault("users", []).append(user)
                    existing_emails.add(user.get("email"))
                elif isinstance(user, dict) and user.get("email") in existing_emails:
                    # Update existing user entry
                    for i, u in enumerate(self._data["users"]):
                        if u.get("email") == user.get("email"):
                            self._data["users"][i].update(user)
                            break

        if "insights" in update and isinstance(update["insights"], list):
            existing_insights = set(self._data.get("insights", []))
            for insight in update["insights"]:
                if insight not in existing_insights:
                    self._data.setdefault("insights", []).append(insight)

        self.save()

    def get_summary(self, max_chars: int = 2000) -> str:
        """Compact summary for injection into system prompt."""
        parts = []

        if self._data.get("server"):
            parts.append(f"Server: {json.dumps(self._data['server'], ensure_ascii=False)}")

        routes = self._data.get("routes", {})
        if routes:
            parts.append(f"Known routes ({len(routes)}):")
            for route, info in list(routes.items())[:15]:
                info_str = json.dumps(info, ensure_ascii=False) if isinstance(info, dict) else str(info)
                parts.append(f"  {route}: {info_str[:80]}")
            if len(routes) > 15:
                parts.append(f"  ... and {len(routes) - 15} more")

        users = self._data.get("users", [])
        if users:
            parts.append(f"Known users ({len(users)}):")
            for u in users[:8]:
                parts.append(f"  {u.get('email', '?')} role={u.get('role', '?')} pw={u.get('password', '?')}")

        fs = self._data.get("file_system", {})
        if fs:
            parts.append(f"File system: {json.dumps(fs, ensure_ascii=False)[:300]}")

        attack = self._data.get("attack_surface", {})
        if attack:
            parts.append(f"Attack surface: {json.dumps(attack, ensure_ascii=False)[:400]}")

        insights = self._data.get("insights", [])
        if insights:
            parts.append(f"Key insights:")
            for i in insights[-5:]:
                parts.append(f"  • {i}")

        summary = "\n".join(parts)
        return summary[:max_chars]

    @property
    def data(self) -> dict:
        return self._data
