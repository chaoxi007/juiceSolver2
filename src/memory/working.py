from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..actions.base import ActionRequest, ActionResult
from ..utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class EndpointInfo:
    status: int
    note: str = ""

    def to_dict(self) -> dict:
        return {"status": self.status, "note": self.note}


@dataclass
class AuthState:
    logged_in: bool = False
    user: str = ""

    def to_dict(self) -> dict:
        return {"logged_in": self.logged_in, "user": self.user}


class WorkingMemory:
    """Per-challenge working memory that auto-extracts key facts from each turn."""

    MAX_FAILED = 15
    MAX_FINDINGS = 12
    MAX_ENDPOINTS_DISPLAY = 10
    MAX_FAILED_DISPLAY = 5
    MAX_FINDINGS_DISPLAY = 8

    def __init__(self, challenge_key: str, log_dir: Path | str | None = None):
        self.challenge_key = challenge_key
        self.discovered_endpoints: dict[str, EndpointInfo] = {}
        self.auth_state = AuthState()
        self.failed_approaches: list[str] = []
        self.key_findings: list[str] = []
        self.turns_used: int = 0
        self.http_requests_made: int = 0

        # Disk persistence for debugging
        self._log_dir: Path | None = None
        if log_dir is not None:
            self._log_dir = Path(log_dir) / "working_memory"
            self._log_dir.mkdir(parents=True, exist_ok=True)

    def absorb(self, turn: int, request: ActionRequest, result: ActionResult) -> None:
        """Extract key facts from a turn's action and result."""
        self.turns_used = turn + 1

        action = request.action
        params = request.params
        data = result.data
        status = result.status

        if action == "http_request":
            self._absorb_http(params, data, status)
        elif action == "login":
            self._absorb_login(params, data, status)
        elif action == "register_user":
            self._absorb_register(params, data, status)
        elif action == "check_solved":
            self._absorb_check_solved(data)

        # Enforce size limits
        if len(self.failed_approaches) > self.MAX_FAILED:
            self.failed_approaches = self.failed_approaches[-self.MAX_FAILED:]
        if len(self.key_findings) > self.MAX_FINDINGS:
            self.key_findings = self.key_findings[-self.MAX_FINDINGS:]

        # Persist to disk for debugging
        self._save_snapshot(turn)

    def _add_finding(self, finding: str) -> None:
        if finding not in self.key_findings:
            self.key_findings.append(finding)
            if len(self.key_findings) > self.MAX_FINDINGS:
                self.key_findings = self.key_findings[-self.MAX_FINDINGS:]

    def _absorb_http(self, params: dict, data: dict, status: str) -> None:
        self.http_requests_made += 1
        method = params.get("method", "GET").upper()
        path = params.get("path", "?")
        # Strip query string for endpoint key to avoid explosion of entries
        base_path = path.split("?")[0]
        ep_key = f"{method} {base_path}"

        if status == "success":
            status_code = data.get("status_code", 0)
            body = str(data.get("body", ""))[:200]
            note = self._classify_response(status_code, body)
            self.discovered_endpoints[ep_key] = EndpointInfo(status=status_code, note=note)

            if status_code >= 400:
                self.failed_approaches.append(f"{ep_key} → {status_code}")
            elif status_code == 200 and len(body) > 50:
                # Record interesting successful responses
                snippet = body[:80].replace("\n", " ")
                self._add_finding(f"{ep_key} → {snippet}...")
        else:
            self.failed_approaches.append(f"{ep_key} → error: {data}")

    def _absorb_login(self, params: dict, data: dict, status: str) -> None:
        email = params.get("email", "?")
        if status == "success" and data.get("authenticated"):
            self.auth_state = AuthState(logged_in=True, user=email)
            self._add_finding(f"Logged in as {email}")
        else:
            self.failed_approaches.append(f"Login failed: {email}")

    def _absorb_register(self, params: dict, data: dict, status: str) -> None:
        email = params.get("email", "?")
        role = params.get("role")
        if status == "success" and data.get("registered"):
            role_info = f" (role={role})" if role else ""
            self._add_finding(f"Registered {email}{role_info}")
        else:
            self.failed_approaches.append(f"Register failed: {email}")

    def _absorb_check_solved(self, data: dict) -> None:
        solved = data.get("solved", False)
        if not solved:
            self._add_finding("check_solved → NOT solved yet")

    @staticmethod
    def _classify_response(status_code: int, body: str) -> str:
        """Generate a short note classifying the HTTP response."""
        if status_code == 200:
            if "token" in body.lower() or "authentication" in body.lower():
                return "auth response"
            if body.strip().startswith("{") or body.strip().startswith("["):
                return "JSON data"
            if "<html" in body.lower():
                return "HTML page"
            return "OK"
        elif status_code == 201:
            return "created"
        elif status_code == 301 or status_code == 302:
            return "redirect"
        elif status_code == 401:
            return "unauthorized"
        elif status_code == 403:
            return "forbidden"
        elif status_code == 404:
            return "not found"
        elif status_code == 500:
            return "server error"
        else:
            return f"status {status_code}"

    def get_summary(self) -> str:
        """Generate a compact text summary for injection into LLM context."""
        parts = [
            f"== Working Memory (Turn {self.turns_used}, "
            f"{self.http_requests_made} HTTP requests) ==",
        ]

        # Auth state
        if self.auth_state.logged_in:
            parts.append(f"Auth: Logged in as {self.auth_state.user}")
        else:
            parts.append("Auth: Not authenticated")

        # Key findings
        if self.key_findings:
            parts.append("Key findings:")
            for f in self.key_findings[-self.MAX_FINDINGS_DISPLAY:]:
                parts.append(f"  - {f}")

        # Discovered endpoints
        if self.discovered_endpoints:
            eps = list(self.discovered_endpoints.items())
            parts.append(f"Endpoints explored ({len(eps)}):")
            for ep, info in eps[-self.MAX_ENDPOINTS_DISPLAY:]:
                parts.append(f"  {ep} → {info.status} {info.note}")

        # Failed approaches
        if self.failed_approaches:
            parts.append(f"Failed approaches ({len(self.failed_approaches)}):")
            for f in self.failed_approaches[-self.MAX_FAILED_DISPLAY:]:
                parts.append(f"  ✗ {f}")

        return "\n".join(parts)

    def to_dict(self) -> dict:
        """Serialize full state for debugging/persistence."""
        return {
            "challenge_key": self.challenge_key,
            "turns_used": self.turns_used,
            "http_requests_made": self.http_requests_made,
            "auth_state": self.auth_state.to_dict(),
            "key_findings": self.key_findings,
            "discovered_endpoints": {
                k: v.to_dict() for k, v in self.discovered_endpoints.items()
            },
            "failed_approaches": self.failed_approaches,
        }

    def _save_snapshot(self, turn: int) -> None:
        """Save a JSON snapshot of working memory to disk for debugging."""
        if self._log_dir is None:
            return
        try:
            snapshot = self.to_dict()
            snapshot["_turn"] = turn
            path = self._log_dir / f"{self.challenge_key}.json"
            path.write_text(
                json.dumps(snapshot, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except Exception as e:
            logger.debug(f"Failed to save working memory snapshot: {e}")
