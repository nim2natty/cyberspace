"""LLM provider abstraction.

Supported providers:
  - ollama     local, offline, free (default - best for learners / the Pi)
  - openai     OpenAI API (gpt-4o-mini etc.)
  - anthropic  Claude API
  - custom     any OpenAI-compatible /chat/completions endpoint

Every provider implements chat(messages, tools, tool_choice) -> response, where
`tools` are cyberspace Tool objects. Each handles tool-calling in its native
format and returns a normalized AgentResponse (text + tool_calls).
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Optional

import httpx

from ..modules.base import Tool


@dataclass
class LLMConfig:
    provider: str = "ollama"            # ollama | openai | anthropic | custom
    model: str = "llama3.1:8b"
    base_url: str = "http://localhost:11434"
    api_key: str = ""
    temperature: float = 0.2
    system_prompt: str = ""

    def to_dict(self) -> dict:
        return field.asdict(self) if hasattr(field, "asdict") else self.__dict__

    @classmethod
    def from_dict(cls, d: dict) -> "LLMConfig":
        return cls(**{k: d[k] for k in cls.__dataclass_fields__ if k in d})


@dataclass
class ToolCall:
    name: str
    arguments: dict


@dataclass
class AgentResponse:
    text: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    raw: Any = None


class LLMProvider:
    """Base provider. Subclasses implement chat()."""
    name = "base"

    def __init__(self, cfg: LLMConfig) -> None:
        self.cfg = cfg
        self.client = httpx.Client(timeout=120.0)

    def chat(self, messages: list[dict], tools: list[Tool]) -> AgentResponse:
        raise NotImplementedError


# --------------------------------------------------------------------------- #
# Ollama (local) - uses its native tool-calling API (llama3.1, qwen2.5, etc.)
# --------------------------------------------------------------------------- #
class OllamaProvider(LLMProvider):
    name = "ollama"

    def chat(self, messages, tools):
        payload = {
            "model": self.cfg.model,
            "messages": messages,
            "stream": False,
            "options": {"temperature": self.cfg.temperature},
        }
        if tools:
            payload["tools"] = [t.to_openai()["function"] for t in tools]
        r = self.client.post(f"{self.cfg.base_url}/api/chat", json=payload)
        r.raise_for_status()
        data = r.json()
        msg = data.get("message", {})
        calls = [
            ToolCall(name=c["function"]["name"],
                     arguments=_safe_json(c["function"].get("arguments", "{}")))
            for c in msg.get("tool_calls", [])
        ]
        return AgentResponse(text=msg.get("content", "") or "", tool_calls=calls, raw=data)


# --------------------------------------------------------------------------- #
# OpenAI-compatible (also used by 'custom' for LM Studio, vLLM, OpenRouter...)
# --------------------------------------------------------------------------- #
class OpenAIProvider(LLMProvider):
    name = "openai"

    def _url(self):
        base = self.cfg.base_url.rstrip("/") if self.cfg.base_url else "https://api.openai.com/v1"
        return f"{base}/chat/completions"

    def chat(self, messages, tools):
        payload = {
            "model": self.cfg.model,
            "messages": messages,
            "temperature": self.cfg.temperature,
        }
        headers = {"Content-Type": "application/json"}
        if self.cfg.api_key:
            headers["Authorization"] = f"Bearer {self.cfg.api_key}"
        if tools:
            payload["tools"] = [t.to_openai() for t in tools]
        r = self.client.post(self._url(), json=payload, headers=headers)
        r.raise_for_status()
        data = r.json()
        choice = data["choices"][0]["message"]
        calls = [
            ToolCall(name=c["function"]["name"],
                     arguments=_safe_json(c["function"].get("arguments", "{}")))
            for c in choice.get("tool_calls", [])
        ]
        return AgentResponse(text=choice.get("content") or "", tool_calls=calls, raw=data)


class AnthropicProvider(LLMProvider):
    name = "anthropic"

    def chat(self, messages, tools):
        url = "https://api.anthropic.com/v1/messages"
        headers = {
            "x-api-key": self.cfg.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        sys_msg = next((m["content"] for m in messages if m["role"] == "system"), "")
        conv = [m for m in messages if m["role"] != "system"]
        payload = {
            "model": self.cfg.model,
            "max_tokens": 2048,
            "temperature": self.cfg.temperature,
            "system": sys_msg,
            "messages": conv,
        }
        if tools:
            payload["tools"] = [
                {"name": t.name, "description": t.description, "input_schema": t.parameters}
                for t in tools
            ]
        r = self.client.post(url, json=payload, headers=headers)
        r.raise_for_status()
        data = r.json()
        text = ""
        calls = []
        for block in data.get("content", []):
            if block["type"] == "text":
                text += block["text"]
            elif block["type"] == "tool_use":
                calls.append(ToolCall(name=block["name"], arguments=block.get("input", {})))
        return AgentResponse(text=text, tool_calls=calls, raw=data)


def _safe_json(s):
    if isinstance(s, dict):
        return s
    try:
        return json.loads(s)
    except Exception:
        return {}


def get_provider(cfg: LLMConfig) -> LLMProvider:
    p = cfg.provider.lower()
    if p == "ollama":
        return OllamaProvider(cfg)
    if p == "anthropic":
        return AnthropicProvider(cfg)
    if p in ("openai", "custom"):
        return OpenAIProvider(cfg)
    raise ValueError(f"unknown provider '{cfg.provider}'")
