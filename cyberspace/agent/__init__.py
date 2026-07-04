"""cyberspace agent package - LLM-agnostic agentic core.

The agent is intentionally provider-agnostic. A learner can point it at a
local Ollama model (free, offline) OR their own API key OR any OpenAI-compatible
HTTP endpoint. All modules register tools here, so once the agent is configured
every platform gains agentic control automatically.

Configure FIRST with:  cyberspace setup
Then chat with:         cyberspace agent
"""
from .core import Agent
from .llm import LLMConfig, get_provider

__all__ = ["Agent", "LLMConfig", "get_provider"]
