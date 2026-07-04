"""Persistence for the agent config (~/.cyberspace/agent.json)."""
from __future__ import annotations

from ..config import AGENT_FILE, ensure_dirs
from .llm import LLMConfig


def load_config() -> LLMConfig | None:
    if not AGENT_FILE.exists():
        return None
    try:
        return LLMConfig.from_dict(__import__("json").loads(AGENT_FILE.read_text()))
    except Exception:
        return None


def save_config(cfg: LLMConfig) -> None:
    ensure_dirs()
    import json
    AGENT_FILE.write_text(json.dumps(cfg.__dict__, indent=2))


def is_configured() -> bool:
    return load_config() is not None
