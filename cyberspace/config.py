"""Paths, defaults, and shared constants for the cyberspace platform."""
from __future__ import annotations

import os
from pathlib import Path

# ~/.cyberspace is the platform home (override with CYBERSPACE_HOME)
HOME = Path(os.environ.get("CYBERSPACE_HOME", Path.home() / ".cyberspace"))

AGENT_FILE = HOME / "agent.json"       # LLM provider/model config (set up first)
MODULES_DIR = HOME / "modules"         # per-module state
LOGS_DIR = HOME / "logs"
CACHE_DIR = HOME / "cache"
STATE_FILE = HOME / "state.json"

DEFAULT_OLLAMA_URL = "http://localhost:11434"

# Curated default model suggestions per provider (learner-friendly).
SUGGESTED_MODELS = {
    "ollama": ["llama3.1:8b", "qwen2.5-coder:7b", "mistral-nemo:7b", "phi3:mini"],
    "openai": ["gpt-4o-mini", "gpt-4o"],
    "anthropic": ["claude-3-5-sonnet-latest", "claude-3-5-haiku-latest"],
    "custom": [],
}


def ensure_dirs() -> None:
    for d in (HOME, MODULES_DIR, LOGS_DIR, CACHE_DIR):
        d.mkdir(parents=True, exist_ok=True)
