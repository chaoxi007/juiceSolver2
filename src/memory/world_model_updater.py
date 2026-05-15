"""WorldModelUpdater: LLM-based post-challenge knowledge extraction."""
from __future__ import annotations

import json

from ..llm.base import LLMMessage, LLMResponse
from ..llm.router import LLMRouter
from ..memory.world_model import WorldModel
from ..utils.logging import get_logger

logger = get_logger(__name__)

EXTRACTION_PROMPT = """\
You are a knowledge extraction agent. Given the conversation history of a security testing session against OWASP Juice Shop, extract ALL useful structural knowledge discovered during this session.

Output a JSON object with these fields (include only fields where you found new information):

{
  "server": {"framework": "...", "version": "...", "auth_mechanism": "...", ...},
  "routes": {
    "/path": {"methods": ["GET"], "auth": "none|user|admin", "notes": "what it does", "status_codes_seen": [200, 401]}
  },
  "users": [
    {"email": "...", "role": "user|admin", "password": "...", "notes": "..."}
  ],
  "file_system": {
    "/ftp/": "directory listing, only .md/.pdf allowed, null byte bypass works",
    "/assets/public/images/uploads/": "user uploaded images"
  },
  "attack_surface": {
    "sqli_endpoints": ["/rest/user/login", "/rest/products/search"],
    "redirect_allowlist": ["https://..."],
    "file_upload": "/file-upload or /b2b/v1/",
    "xss_sinks": ["..."],
    "other": "..."
  },
  "insights": [
    "Short actionable insight about the target, e.g. 'The redirect endpoint checks URLs against a whitelist stored in the frontend JS bundle'",
    "Another insight..."
  ]
}

Rules:
- Only include FACTS observed in the conversation, not speculation.
- For passwords, only include confirmed working credentials.
- For routes, include the HTTP status codes you actually saw.
- Insights should be concise, actionable, and useful for solving OTHER challenges.
- If the challenge was solved, note HOW it was solved in insights.
- If the challenge failed, note WHY it failed and what was learned.
- Reply with ONLY the JSON object, no other text.
"""


class WorldModelUpdater:
    """Extracts structured knowledge from a challenge session and merges into world model."""

    def __init__(self, llm: LLMRouter, world_model: WorldModel):
        self.llm = llm
        self.world_model = world_model

    async def update_from_session(
        self,
        challenge_key: str,
        conversation: list[LLMMessage],
        solved: bool,
    ) -> None:
        """Run LLM extraction on the conversation and merge results."""
        if not conversation:
            return

        # Build extraction prompt with conversation summary
        conv_text = self._format_conversation(conversation)

        messages = [
            LLMMessage(role="system", content=EXTRACTION_PROMPT),
            LLMMessage(
                role="user",
                content=f"Challenge: {challenge_key} (solved={solved})\n\nConversation:\n{conv_text}",
            ),
        ]

        try:
            resp: LLMResponse = await self.llm.complete(
                messages,
                task_type="extraction",
                temperature=0.2,
                max_tokens=2048,
                json_mode=True,
            )

            update = json.loads(resp.content)
            if isinstance(update, dict):
                self.world_model.merge_update(update)
                route_count = len(update.get("routes", {}))
                user_count = len(update.get("users", []))
                insight_count = len(update.get("insights", []))
                logger.info(
                    f"  World model updated from {challenge_key}: "
                    f"+{route_count} routes, +{user_count} users, +{insight_count} insights"
                )
        except json.JSONDecodeError as e:
            logger.warning(f"  World model extraction failed (invalid JSON): {e}")
        except Exception as e:
            logger.warning(f"  World model extraction failed: {e}")

    def _format_conversation(self, messages: list[LLMMessage], max_chars: int = 6000) -> str:
        """Format conversation for extraction, keeping within token budget."""
        parts = []
        total = 0
        for msg in messages:
            if msg.role == "system":
                continue
            prefix = "AGENT" if msg.role == "assistant" else "RESULT"
            content = msg.content[:500]  # truncate individual messages
            line = f"[{prefix}] {content}"
            if total + len(line) > max_chars:
                parts.append("... (conversation truncated)")
                break
            parts.append(line)
            total += len(line)
        return "\n".join(parts)
