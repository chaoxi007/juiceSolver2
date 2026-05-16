from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass
class ProviderConfig:
    model: str
    api_key: str = ""
    base_url: str = ""

    def validate(self) -> None:
        if not self.api_key:
            raise ValueError(
                f"Please set a valid api_key for model '{self.model}' in config.yaml"
            )


@dataclass
class LLMConfig:
    default_provider: str
    providers: dict[str, ProviderConfig] = field(default_factory=dict)
    routing: dict[str, str] = field(default_factory=dict)


@dataclass
class AgentConfig:
    max_retries: int = 5
    max_turns_per_challenge: int = 25
    delay_between_requests_ms: int = 200
    max_total_time_minutes: int = 120
    memory_file: str = "data/memory.json"
    log_dir: str = "logs"


@dataclass
class Config:
    target_url: str = "http://localhost:3000"
    llm: LLMConfig = field(default_factory=lambda: LLMConfig(default_provider="claude"))
    agent: AgentConfig = field(default_factory=AgentConfig)
    log_level: str = "INFO"
    persistence_file: str = "session_state.json"


def _resolve_env(value: str) -> str:
    """Resolve ${ENV_VAR} placeholders to environment variable values."""
    if value.startswith("${") and value.endswith("}"):
        env_name = value[2:-1]
        return os.environ.get(env_name, "")
    return value


def load_config(path: Path | str = "config.yaml") -> Config:
    path = Path(path)
    if not path.exists():
        return Config()

    with open(path, encoding="utf-8") as f:
        raw: dict[str, Any] = yaml.safe_load(f) or {}

    providers = {}
    for name, pconf in raw.get("llm", {}).get("providers", {}).items():
        api_key = _resolve_env(pconf.get("api_key", ""))
        base_url = _resolve_env(pconf.get("base_url", ""))
        providers[name] = ProviderConfig(
            model=pconf["model"],
            api_key=api_key,
            base_url=base_url,
        )

    llm_raw = raw.get("llm", {})
    llm = LLMConfig(
        default_provider=llm_raw.get("default_provider", "claude"),
        providers=providers,
        routing=llm_raw.get("routing", {}),
    )

    agent_raw = raw.get("agent", {})
    agent = AgentConfig(
        max_retries=agent_raw.get("max_retries", 5),
        max_turns_per_challenge=agent_raw.get("max_turns_per_challenge", 25),
        delay_between_requests_ms=agent_raw.get("delay_between_requests_ms", 200),
        max_total_time_minutes=agent_raw.get("max_total_time_minutes", 120),
        memory_file=agent_raw.get("memory_file", "data/memory.json"),
        log_dir=agent_raw.get("log_dir", "logs"),
    )

    return Config(
        target_url=raw.get("target", {}).get("base_url", "http://localhost:3000"),
        llm=llm,
        agent=agent,
        log_level=raw.get("logging", {}).get("level", "INFO"),
        persistence_file=raw.get("persistence", {}).get("state_file", "session_state.json"),
    )
