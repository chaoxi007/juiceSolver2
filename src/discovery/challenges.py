from __future__ import annotations

from dataclasses import dataclass

from ..http_toolkit.client import HttpClient
from ..utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class Challenge:
    id: int
    key: str
    name: str
    category: str
    difficulty: int
    description: str
    solved: bool
    hint: str = ""

    def __repr__(self) -> str:
        status = "[SOLVED]" if self.solved else f"[{'*' * self.difficulty}]"
        return f"{status} {self.name} ({self.category})"


class ChallengeDiscovery:
    def __init__(self, http: HttpClient):
        self.http = http

    async def fetch_all(self) -> list[Challenge]:
        resp = await self.http.get("/api/Challenges/")
        if resp.status_code != 200:
            logger.error(f"Failed to fetch challenges: {resp.status_code}")
            return []

        data = resp.json().get("data", [])
        challenges = []
        for item in data:
            challenges.append(Challenge(
                id=item["id"],
                key=item.get("key", ""),
                name=item.get("name", ""),
                category=item.get("category", ""),
                difficulty=item.get("difficulty", 1),
                description=item.get("description", ""),
                solved=item.get("solved", False),
                hint=item.get("hint", ""),
            ))

        logger.info(f"Discovered {len(challenges)} challenges, {sum(1 for c in challenges if c.solved)} already solved")
        return challenges

    async def check_solved(self, challenge_id: int) -> bool:
        resp = await self.http.get("/api/Challenges/")
        if resp.status_code != 200:
            return False
        data = resp.json().get("data", [])
        for item in data:
            if item["id"] == challenge_id:
                return item.get("solved", False)
        return False
