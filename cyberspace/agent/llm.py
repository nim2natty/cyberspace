"""LLM provider abstraction.

cyberspace can talk to almost any LLM. See ``agent/providers.py`` for the catalog
of supported providers. Each falls into one of three API dialects:

  - ollama     Ollama's native /api/chat (local, free)
  - openai     OpenAI-compatible /chat/completions (OpenAI, z.ai, DeepSeek,
               Groq, OpenRouter, Together, Mistral, xAI, Gemini, Perplexity,
               LM Studio, vLLM, RoboDaddy-trained models, and any custom one)
  - anthropic  Claude's native /v1/messages

Every provider implements chat(messages, tools) -> AgentResponse, where `tools`
are cyberspace Tool objects. Each handles tool-calling in its native format and
returns a normalized AgentResponse (text + tool_calls). Network/HTTP failures are
translated into a single ``ProviderError`` with only the information the operator
needs to fix the problem.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Optional

import httpx

from ..modules.base import Tool
from .providers import get_spec


class ProviderError(RuntimeError):
    """A clean, human-readable error from an LLM provider (no traceback noise)."""


@dataclass
class LLMConfig:
    provider: str = "ollama"            # any key from the providers catalog
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
    id: str = ""


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

    def _post(self, url: str, payload: dict, headers: Optional[dict] = None) -> dict:
        """POST JSON with clean, operator-facing error translation."""
        provider = self.cfg.provider or self.name
        try:
            r = self.client.post(url, json=payload, headers=headers or {})
            r.raise_for_status()
            return r.json()
        except httpx.HTTPStatusError as e:
            raise ProviderError(_explain_http(provider, url, e.response))
        except httpx.ConnectError:
            raise ProviderError(
                f"Could not connect to {provider} at {url}.\n"
                f"  Check the base URL is correct and the service is reachable "
                f"(for local servers, make sure it is running).")
        except httpx.TimeoutException:
            raise ProviderError(
                f"{provider} timed out (120s) at {url}. Try again, switch to a "
                f"smaller/faster model, or check your network.")
        except httpx.HTTPError as e:
            raise ProviderError(f"{provider} request failed: {e}")


def _explain_http(provider: str, url: str, resp) -> str:
    code = resp.status_code
    body = ""
    try:
        body = (resp.text or "").strip().replace("\n", " ")[:240]
    except Exception:
        pass
    if code in (401, 403):
        hint = (f"{provider} rejected your API key (HTTP {code}). Re-run "
                f"`cyberspace setup` and paste a valid key for this provider.")
    elif code == 404:
        hint = (f"{provider} returned 'not found' (HTTP 404) at {url}. "
                f"Check the model name and the base URL.")
    elif code == 429:
        hint = (f"{provider} rate-limited you (HTTP 429). Slow down, or check "
                f"your billing/quota on the provider dashboard.")
    elif code in (400, 422):
        hint = (f"{provider} rejected the request (HTTP {code}). Usually a wrong "
                f"or unsupported model name, or the model can't call tools.")
    elif code in (500, 502, 503, 504):
        hint = (f"{provider} had a server error (HTTP {code}). Try again shortly.")
    else:
        hint = f"{provider} returned HTTP {code}."
    tail = f"\n  endpoint: {url}"
    if body:
        tail += f"\n  response: {body}"
    return hint + tail



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
        url = f"{self.cfg.base_url.rstrip('/')}/api/chat"
        data = self._post(url, payload)
        msg = data.get("message", {})
        calls = [
            ToolCall(name=c["function"]["name"], id=c.get("id", f"call_{i}"),
                     arguments=_safe_json(c["function"].get("arguments", "{}")))
            for i, c in enumerate(msg.get("tool_calls", []))
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
        data = self._post(self._url(), payload, headers)
        choice = data["choices"][0]["message"]
        calls = [
            ToolCall(name=c["function"]["name"], id=c.get("id", f"call_{i}"),
                     arguments=_safe_json(c["function"].get("arguments", "{}")))
            for i, c in enumerate(choice.get("tool_calls", []))
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
        conv = _anthropic_messages([m for m in messages if m["role"] != "system"])
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
        r = self._post(url, payload, headers)
        data = r
        text = ""
        calls = []
        for block in data.get("content", []):
            if block["type"] == "text":
                text += block["text"]
            elif block["type"] == "tool_use":
                calls.append(ToolCall(name=block["name"], arguments=block.get("input", {}),
                                      id=block.get("id", "")))
        return AgentResponse(text=text, tool_calls=calls, raw=data)


def _safe_json(s):
    if isinstance(s, dict):
        return s
    try:
        return json.loads(s)
    except Exception:
        return {}


def _anthropic_messages(messages: list[dict]) -> list[dict]:
    """Translate the internal OpenAI-like tool transcript to Anthropic blocks."""
    out = []
    for msg in messages:
        role = msg.get("role")
        if role == "assistant" and msg.get("tool_calls"):
            blocks = []
            if msg.get("content"):
                blocks.append({"type": "text", "text": msg["content"]})
            for call in msg["tool_calls"]:
                fn = call.get("function", {})
                blocks.append({"type": "tool_use", "id": call.get("id", ""),
                               "name": fn.get("name", ""),
                               "input": _safe_json(fn.get("arguments", {}))})
            out.append({"role": "assistant", "content": blocks})
        elif role == "tool":
            block = {"type": "tool_result", "tool_use_id": msg.get("tool_call_id", ""),
                     "content": str(msg.get("content", ""))}
            if out and out[-1].get("role") == "user" and isinstance(out[-1].get("content"), list):
                out[-1]["content"].append(block)
            else:
                out.append({"role": "user", "content": [block]})
        else:
            out.append({"role": role, "content": msg.get("content", "")})
    return out


def get_provider(cfg: LLMConfig) -> LLMProvider:
    """Return the right client for the configured provider.

    Routing is driven by the provider's API dialect in the catalog, so any
    OpenAI-compatible provider (z.ai, Groq, DeepSeek, ...) "just works" once the
    base URL + model are saved in the config.
    """
    p = (cfg.provider or "").lower()
    spec = get_spec(p)
    api_style = spec.api_style if spec else "openai"

    # OpenAI-compatible providers: fill in the catalog default base URL if the
    # config didn't set one (keeps saved configs minimal).
    if api_style == "openai" and not cfg.base_url and spec and spec.base_url:
        cfg.base_url = spec.base_url

    if api_style == "ollama":
        return OllamaProvider(cfg)
    if api_style == "anthropic":
        return AnthropicProvider(cfg)
    return OpenAIProvider(cfg)


def chat_with_failover(provider: LLMProvider, messages: list[dict], tools: list[Tool],
                       console=None) -> AgentResponse:
    """Continue a request on another current model after a model-specific failure."""
    try:
        return provider.chat(messages, tools)
    except ProviderError as first_error:
        text = str(first_error).lower()
        # A different model cannot repair credentials, quota, or connectivity.
        if any(marker in text for marker in ("http 401", "http 403", "http 429",
                                              "could not connect", "timed out")):
            raise
        candidates = _available_models(provider)
        original = provider.cfg.model
        alternatives = [m for m in candidates if m and m != original][:5]
        if not alternatives:
            raise
        if console:
            console.print(f"[yellow]Model {original} failed; preserving the objective and trying "
                          f"{len(alternatives)} available alternative(s).[/yellow]")
        last_error = first_error
        for model in alternatives:
            provider.cfg.model = model
            if console:
                console.print(f"[cyan]↻ model failover:[/cyan] {original} → [bold]{model}[/bold]")
            try:
                response = provider.chat(messages, tools)
                if console:
                    console.print(f"[green]✓ continued with {model}[/green]")
                return response
            except ProviderError as exc:
                last_error = exc
                if console:
                    console.print(f"[dim]  {model} unavailable; trying next model[/dim]")
        provider.cfg.model = original
        raise last_error


def _available_models(provider: LLMProvider) -> list[str]:
    """Discover live model IDs, with the reviewed provider catalog as fallback."""
    spec = get_spec(provider.cfg.provider)
    fallback = list(spec.models) if spec else []
    try:
        if spec and spec.api_style == "ollama":
            url = f"{provider.cfg.base_url.rstrip('/')}/api/tags"
            data = provider.client.get(url).json()
            live = [m.get("name", "") for m in data.get("models", [])]
        else:
            if spec and spec.api_style == "anthropic":
                url = "https://api.anthropic.com/v1/models"
                headers = {"x-api-key": provider.cfg.api_key,
                           "anthropic-version": "2023-06-01"}
            else:
                url = f"{provider.cfg.base_url.rstrip('/')}/models"
                headers = ({"Authorization": f"Bearer {provider.cfg.api_key}"}
                           if provider.cfg.api_key else {})
            response = provider.client.get(url, headers=headers)
            response.raise_for_status()
            live = [m.get("id", "") for m in response.json().get("data", [])]
        return list(dict.fromkeys([*live, *fallback]))
    except Exception:
        return fallback
