from __future__ import annotations

import argparse
import asyncio
import sys
import time

from .agent.loop import AgentLoop
from .discovery.challenges import ChallengeDiscovery
from .discovery.prioritizer import Prioritizer
from .http_toolkit.client import HttpClient
from .llm.router import LLMRouter
from .run_log.action_logger import ActionLogger
from .memory.store import MemoryStore
from .progress.reporter import print_summary
from .progress.tracker import ProgressTracker
from .utils.config import load_config
from .utils.logging import get_logger, setup_logging

logger = get_logger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Automated OWASP Juice Shop challenge solver"
    )
    parser.add_argument(
        "--target", "-t",
        default=None,
        help="Juice Shop base URL (e.g. http://localhost:3000)",
    )
    parser.add_argument(
        "--config", "-c",
        default="config.yaml",
        help="Path to config file (default: config.yaml)",
    )
    parser.add_argument(
        "--log-level", "-l",
        default=None,
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Log level override",
    )
    parser.add_argument(
        "--max-challenges", "-n",
        type=int,
        default=None,
        help="Max number of challenges to attempt",
    )
    return parser.parse_args()


async def async_main() -> None:
    args = parse_args()
    config = load_config(args.config)

    if args.target:
        config.target_url = args.target
    if args.log_level:
        config.log_level = args.log_level

    setup_logging(config.log_level)
    logger.info(f"Target: {config.target_url}")

    try:
        llm = LLMRouter(config)
    except ValueError as e:
        print(f"LLM configuration error: {e}", file=sys.stderr)
        sys.exit(1)

    http = HttpClient(config.target_url, delay_ms=config.agent.delay_between_requests_ms)
    discovery = ChallengeDiscovery(http)
    memory = MemoryStore(config.agent.memory_file)
    action_logger = ActionLogger(config.agent.log_dir)
    tracker = ProgressTracker()

    from .memory.world_model import WorldModel
    world_model = WorldModel()

    agent = AgentLoop(
        config=config,
        llm=llm,
        http=http,
        discovery=discovery,
        memory=memory,
        action_logger=action_logger,
        world_model=world_model,
    )

    challenges = await discovery.fetch_all()
    if not challenges:
        logger.error("No challenges found. Is Juice Shop running?")
        await http.close()
        return

    # Auto-populate target_profile on first run
    if not memory.read("target_profile"):
        memory.write("target_profile", "base_url", config.target_url)
        memory.write("target_profile", "total_challenges", len(challenges))
        categories = list({c.category for c in challenges})
        memory.write("target_profile", "categories", categories)

    prioritizer = Prioritizer()
    queue = prioritizer.sort(challenges)
    solved_keys = {c.key for c in challenges if c.solved}
    queue = prioritizer.reorder_with_dependencies(queue, solved_keys)

    if args.max_challenges:
        queue = queue[: args.max_challenges]

    max_total_seconds = config.agent.max_total_time_minutes * 60
    session_start = time.time()
    logger.info(f"Attempting {len(queue)} unsolved challenges (max_turns={config.agent.max_turns_per_challenge}, timeout={config.agent.max_total_time_minutes}min)")

    from pathlib import Path
    state_path = Path(config.persistence_file)
    tracker.load_state(state_path)

    from rich.console import Console
    _console = Console()

    for challenge in queue:
        # Global timeout check
        elapsed = time.time() - session_start
        remaining = max_total_seconds - elapsed
        if remaining <= 0:
            logger.warning(f"Global timeout reached ({config.agent.max_total_time_minutes}min). Skipping remaining challenges.")
            _console.print(f"  [yellow]TIMEOUT[/yellow] Global time limit reached after {elapsed:.0f}s")
            break

        start = time.time()
        solved = await agent.run_challenge(challenge, deadline=session_start + max_total_seconds)
        duration = time.time() - start

        status = "solved" if solved else "failed"
        tracker.record(challenge, status, "agent", attempts=1, duration=duration)
        tracker.save_state(state_path)

        status_str = "[green]SOLVED[/green]" if solved else "[red]FAILED[/red]"
        _console.print(f"  {status_str} {challenge.name} ({duration:.1f}s)")

    print_summary(tracker)
    action_logger.close()
    await agent.browser.close()
    await http.close()


def main() -> None:
    asyncio.run(async_main())


if __name__ == "__main__":
    main()
