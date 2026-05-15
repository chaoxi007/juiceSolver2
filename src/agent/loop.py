from __future__ import annotations

import asyncio
import time

from ..actions.auth import LoginHandler, RegisterUserHandler
from ..actions.analyze_js import AnalyzeJsHandler
from ..actions.browser import BrowserNavigateHandler
from ..actions.check_solved import CheckSolvedHandler
from ..actions.give_up import GiveUpHandler
from ..actions.http_request import HttpRequestHandler
from ..actions.memory_actions import ReadMemoryHandler, WriteMemoryHandler
from ..actions.think import ThinkHandler
from ..actions.use_skill import UseSkillHandler
from ..browser.session import BrowserSession
from ..discovery.challenges import Challenge, ChallengeDiscovery
from ..http_toolkit.client import HttpClient
from ..llm.base import LLMMessage
from ..llm.router import LLMRouter
from ..run_log.action_logger import ActionLogger
from ..memory.store import MemoryStore
from ..memory.working import WorkingMemory
from ..memory.world_model import WorldModel
from ..memory.world_model_updater import WorldModelUpdater
from ..utils.config import Config
from ..utils.logging import get_logger
from .prompt import build_system_prompt
from .protocol import Protocol
from .window import ConversationWindow

logger = get_logger(__name__)

# Sliding window size: set to a large number to disable sliding and keep full history for LLM Prompt Caching
WINDOW_SIZE = 100


class AgentLoop:
    def __init__(
        self,
        config: Config,
        llm: LLMRouter,
        http: HttpClient,
        discovery: ChallengeDiscovery,
        memory: MemoryStore,
        action_logger: ActionLogger,
        world_model: WorldModel | None = None,
    ):
        self.config = config
        self.llm = llm
        self.http = http
        self.discovery = discovery
        self.memory = memory
        self.action_logger = action_logger
        self.max_turns = config.agent.max_turns_per_challenge
        self.browser = BrowserSession(config.target_url)
        self.world_model = world_model or WorldModel()
        self.world_model_updater = WorldModelUpdater(llm, self.world_model)

        self.protocol = Protocol()
        self._register_handlers()

    def _register_handlers(self) -> None:
        for handler in [
            HttpRequestHandler(),
            LoginHandler(),
            RegisterUserHandler(),
            CheckSolvedHandler(),
            ReadMemoryHandler(),
            WriteMemoryHandler(),
            ThinkHandler(),
            GiveUpHandler(),
            BrowserNavigateHandler(),
            AnalyzeJsHandler(),
        ]:
            self.protocol.register(handler)
        # UseSkillHandler needs Protocol reference to dispatch sub-actions
        self.protocol.register(UseSkillHandler(self.protocol))

    def _build_context(self, challenge: Challenge) -> dict:
        return {
            "http": self.http,
            "browser": self.browser,
            "memory": self.memory,
            "discovery": self.discovery,
            "challenge_id": challenge.id,
        }

    async def _call_llm_with_retry(self, messages, max_retries: int = 3):
        for attempt in range(max_retries):
            try:
                return await self.llm.complete(
                    messages, task_type="agent", temperature=0.7, max_tokens=2048, json_mode=True
                )
            except Exception as e:
                logger.warning(f"  LLM call failed (attempt {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(5 * (attempt + 1))
        return None

    def _build_messages(
        self,
        system_prompt: str,
        working_memory: WorkingMemory,
        conv_window: ConversationWindow,
    ) -> list[LLMMessage]:
        """Assemble context optimized for LLM Prompt Caching: Static Prefix + Full History + Dynamic Tail."""
        messages = [LLMMessage(role="system", content=system_prompt)]

        # Append the full history of past turns. Since we don't drop old turns, 
        # this entire prefix perfectly matches across turns, maximizing cache hits!
        messages.extend(conv_window.get_messages())

        # The Working Memory changes every turn, so it MUST be placed at the very end 
        # to prevent it from breaking the cache prefix.
        if conv_window.size == 0:
            messages.append(LLMMessage(role="user", content="Begin. Solve this challenge."))
        else:
            latest_prompt = f"Previous findings summary:\n{working_memory.get_summary()}\n\nWhat is your next action? Reply with exactly one JSON object."
            messages.append(LLMMessage(role="user", content=latest_prompt))

        return messages

    async def run_challenge(self, challenge: Challenge, deadline: float | None = None) -> bool:
        logger.info(f"Starting challenge: {challenge.name} ({challenge.category}, difficulty {challenge.difficulty})")

        # Layer 3: Long-term memory → injected into system prompt
        memory_context = self.memory.get_relevant(challenge.category, challenge.key)
        world_summary = self.world_model.get_summary()
        system_prompt = build_system_prompt(challenge, memory_context, self.max_turns, world_summary)

        # Layer 2: Working memory (per-challenge, auto-extracted, persisted to disk)
        working_memory = WorkingMemory(
            challenge_key=challenge.key,
            log_dir=self.config.agent.log_dir,
        )

        # Layer 1: Conversation window (sliding, last K turns)
        conv_window = ConversationWindow(max_turns=WINDOW_SIZE)

        context = self._build_context(challenge)
        recent_actions: list[str] = []  # track action+key for repetition detection

        for turn in range(self.max_turns):
            # Check global deadline before each turn
            if deadline is not None and time.time() >= deadline:
                logger.warning(f"  Global deadline reached during turn {turn}, aborting challenge")
                self.memory.write("attack_results", challenge.key, {
                    "solved": False,
                    "category": challenge.category,
                    "timeout": True,
                })
                return False

            # Build three-tier context
            messages = self._build_messages(system_prompt, working_memory, conv_window)

            resp = await self._call_llm_with_retry(messages)
            if resp is None:
                logger.error("  LLM call failed after retries, skipping challenge")
                return False

            assistant_content = resp.content
            assistant_msg = LLMMessage(role="assistant", content=assistant_content)

            request = self.protocol.parse(assistant_content)
            if request is None:
                error_msg = '{"status":"error","error":"Invalid JSON. Reply with exactly one JSON object: {\\\"action\\\": \\\"...\\\", \\\"params\\\": {...}}"}'
                result_msg = LLMMessage(role="user", content=error_msg)
                conv_window.append(assistant_msg, result_msg)
                logger.warning(f"  Turn {turn}: invalid JSON from LLM")
                continue

            logger.info(f"  Turn {turn}: {request.action} {_summarize_params(request.params)}")

            if request.action == "give_up":
                reason = request.params.get("reason", "")
                logger.info(f"  Agent gave up: {reason}")
                self.memory.write("attack_results", challenge.key, {
                    "solved": False,
                    "category": challenge.category,
                    "gave_up_reason": reason,
                })
                await self._update_world_model(challenge.key, conv_window, False)
                return False

            t0 = time.perf_counter()
            result = await self.protocol.dispatch(request, context)
            duration_ms = (time.perf_counter() - t0) * 1000

            self.action_logger.log(
                challenge_key=challenge.key,
                turn=turn,
                action=request.action,
                params=request.params,
                result_status=result.status,
                result_data=result.data if result.status == "success" else result.error,
                duration_ms=duration_ms,
            )

            result_msg = LLMMessage(role="user", content=self.protocol.format_result(result))

            # Repetition detection: if same action+path repeated 3+ times, inject warning
            action_key = f"{request.action}:{request.params.get('path', request.params.get('skill', ''))}"
            recent_actions.append(action_key)
            if len(recent_actions) >= 3 and len(set(recent_actions[-3:])) == 1:
                result_msg = LLMMessage(
                    role="user",
                    content=self.protocol.format_result(result)
                    + '\n\n⚠️ WARNING: You have repeated the same action 3 times with no progress. '
                    'You MUST try a completely different approach, action, or path. '
                    'If you are stuck, use "give_up".',
                )
                logger.warning(f"  Repetition detected at turn {turn}: {action_key}")

            # Update Layer 2: absorb key facts from this turn
            working_memory.absorb(turn, request, result)

            # Update Layer 1: add to sliding window (auto-trims old turns)
            conv_window.append(assistant_msg, result_msg)

            # Check if challenge was solved (either via check_solved or use_skill)
            solved = False
            if request.action == "check_solved" and result.data.get("solved"):
                solved = True
            elif request.action == "use_skill" and result.data.get("solved"):
                solved = True

            if solved:
                logger.info(f"  Challenge SOLVED in {turn + 1} turns!")
                self.memory.write("attack_results", challenge.key, {
                    "solved": True,
                    "category": challenge.category,
                    "turns_used": turn + 1,
                })
                await self._update_world_model(challenge.key, conv_window, True)
                return True

        logger.warning(f"  Max turns ({self.max_turns}) exhausted")
        self.memory.write("attack_results", challenge.key, {
            "solved": False,
            "category": challenge.category,
            "exhausted_turns": True,
        })
        await self._update_world_model(challenge.key, conv_window, False)
        return False

    async def _update_world_model(
        self, challenge_key: str, conv_window: ConversationWindow, solved: bool
    ) -> None:
        """Post-challenge: extract knowledge into world model."""
        try:
            messages = conv_window.get_messages()
            await self.world_model_updater.update_from_session(challenge_key, messages, solved)
        except Exception as e:
            logger.warning(f"  World model update failed: {e}")


def _summarize_params(params: dict) -> str:
    if not params:
        return ""
    parts = []
    for k, v in list(params.items())[:3]:
        sv = str(v)
        if len(sv) > 40:
            sv = sv[:37] + "..."
        parts.append(f"{k}={sv}")
    return "(" + ", ".join(parts) + ")"
