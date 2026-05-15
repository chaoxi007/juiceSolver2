from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from ..discovery.challenges import Challenge
from ..utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class AttemptRecord:
    challenge_key: str
    challenge_name: str
    category: str
    difficulty: int
    solver_used: str
    status: Literal["solved", "failed", "skipped"]
    attempts: int
    duration_seconds: float
    evidence: str = ""
    error: str = ""


class ProgressTracker:
    def __init__(self):
        self.records: list[AttemptRecord] = []
        self.start_time: float = time.time()
        self._solved_keys: set[str] = set()

    def record(
        self,
        challenge: Challenge,
        status: Literal["solved", "failed", "skipped"],
        solver_name: str,
        attempts: int,
        duration: float,
        evidence: str = "",
        error: str = "",
    ) -> None:
        rec = AttemptRecord(
            challenge_key=challenge.key,
            challenge_name=challenge.name,
            category=challenge.category,
            difficulty=challenge.difficulty,
            solver_used=solver_name,
            status=status,
            attempts=attempts,
            duration_seconds=duration,
            evidence=evidence,
            error=error,
        )
        self.records.append(rec)
        if status == "solved":
            self._solved_keys.add(challenge.key)

    @property
    def solved_keys(self) -> set[str]:
        return self._solved_keys

    @property
    def total(self) -> int:
        return len(self.records)

    @property
    def solved_count(self) -> int:
        return sum(1 for r in self.records if r.status == "solved")

    @property
    def failed_count(self) -> int:
        return sum(1 for r in self.records if r.status == "failed")

    @property
    def elapsed(self) -> float:
        return time.time() - self.start_time

    def stats_by_category(self) -> dict[str, dict[str, int]]:
        result: dict[str, dict[str, int]] = {}
        for r in self.records:
            cat = result.setdefault(r.category, {"solved": 0, "failed": 0, "skipped": 0})
            cat[r.status] += 1
        return result

    def stats_by_difficulty(self) -> dict[int, dict[str, int]]:
        result: dict[int, dict[str, int]] = {}
        for r in self.records:
            diff = result.setdefault(r.difficulty, {"solved": 0, "failed": 0, "skipped": 0})
            diff[r.status] += 1
        return result

    def save_state(self, path: Path) -> None:
        state = {
            "solved_keys": list(self._solved_keys),
            "records": [
                {
                    "key": r.challenge_key,
                    "name": r.challenge_name,
                    "status": r.status,
                    "solver": r.solver_used,
                    "attempts": r.attempts,
                }
                for r in self.records
            ],
        }
        path.write_text(json.dumps(state, indent=2))
        logger.debug(f"State saved to {path}")

    def load_state(self, path: Path) -> None:
        if not path.exists():
            return
        state = json.loads(path.read_text())
        self._solved_keys = set(state.get("solved_keys", []))
        logger.info(f"Resumed state: {len(self._solved_keys)} previously solved")
