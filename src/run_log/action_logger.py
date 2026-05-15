from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..utils.logging import get_logger

logger = get_logger(__name__)


class ActionLogger:
    def __init__(self, log_dir: Path | str = "logs"):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.log_file = self.log_dir / f"run_{timestamp}.jsonl"
        self._file = open(self.log_file, "a", encoding="utf-8")
        logger.info(f"Action log: {self.log_file}")

    def log(
        self,
        challenge_key: str,
        turn: int,
        action: str,
        params: dict,
        result_status: str,
        result_data: Any,
        duration_ms: float,
    ) -> None:
        entry = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "challenge": challenge_key,
            "turn": turn,
            "action": action,
            "params": params,
            "result_status": result_status,
            "result_data": self._truncate(result_data),
            "duration_ms": round(duration_ms, 1),
        }
        self._file.write(json.dumps(entry, ensure_ascii=False) + "\n")
        self._file.flush()

    def _truncate(self, data: Any, max_len: int = 2000) -> Any:
        s = json.dumps(data, ensure_ascii=False) if not isinstance(data, str) else data
        if len(s) > max_len:
            return s[:max_len] + "...[truncated]"
        return data

    def close(self) -> None:
        self._file.close()
