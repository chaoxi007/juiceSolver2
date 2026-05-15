from __future__ import annotations

import logging
from rich.logging import RichHandler
from rich.console import Console

console = Console()


def setup_logging(level: str = "INFO") -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format="%(message)s",
        datefmt="[%X]",
        handlers=[RichHandler(console=console, rich_tracebacks=True)],
    )


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
