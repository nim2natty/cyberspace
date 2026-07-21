"""Catalog of LLM providers cyberspace can drive.

Most modern LLM APIs expose an OpenAI-compatible ``/chat/completions`` endpoint
(z.ai, DeepSeek, Groq, OpenRouter, Together, Mistral, xAI, Gemini, Perplexity,
LM Studio, vLLM ...), so a single OpenAI-style client covers almost everything.
Anthropic uses its own native API; Ollama uses its own. This catalog records, for
every provider we support, the one piece of knowledge the user should NOT have to
look up: the API dialect, the default base URL, the env var that commonly holds
the key, and a few good *agentic* (tool-calling) models.

The setup wizard (``cyberspace setup``) reads this so the user only ever types a
number + their API key. ``cyberspace providers`` lists it for reference.
"""
from __future__ import annotations

from dataclasses import dataclass, field

DEFAULT_OLLAMA_URL = "http://localhost:11434"


@dataclass
class ProviderSpec:
    """Everything cyberspace needs to connect to one LLM provider."""
    key: str                       # stored as LLMConfig.provider
    display: str                   # shown in menus
    api_style: str                 # "ollama" | "openai" | "anthropic"
    base_url: str = ""             # default endpoint (blank = provider default)
    needs_key: bool = True
    key_url: str = ""              # where the user signs up / gets a key
    env_key: str = ""              # env var that may already hold the key
    models: list[str] = field(default_factory=list)  # suggested agentic models
    note: str = ""
    local: bool = False


CATALOG: list[ProviderSpec] = [
    ProviderSpec(
        "ollama", "Ollama (local, free, offline)", "ollama",
        base_url=DEFAULT_OLLAMA_URL, needs_key=False, local=True,
        models=["llama3.1:8b", "qwen2.5-coder:7b", "mistral-nemo:7b", "phi3:mini"],
        note="Best for the cyberdeck / Pi. Runs on your own hardware."),
    ProviderSpec(
        "openai", "OpenAI (GPT)", "openai", base_url="https://api.openai.com/v1",
        key_url="https://platform.openai.com/api-keys", env_key="OPENAI_API_KEY",
        models=["gpt-4o-mini", "gpt-4o", "o3-mini"],
        note="GPT models. Strong, reliable tool-calling."),
    ProviderSpec(
        "anthropic", "Anthropic (Claude)", "anthropic",
        key_url="https://console.anthropic.com/settings/keys", env_key="ANTHROPIC_API_KEY",
        models=["claude-3-5-sonnet-latest", "claude-3-5-haiku-latest"],
        note="Native Claude API - excellent reasoning."),
    ProviderSpec(
        "zai", "z.ai (GLM)", "openai", base_url="https://api.z.ai/api/paas/v4",
        key_url="https://z.ai/manage-apikey/apikey-list", env_key="ZAI_API_KEY",
        models=["glm-4.6", "glm-4.5-air", "glm-4-flash"],
        note="Zhipu GLM models. OpenAI-compatible."),
    ProviderSpec(
        "deepseek", "DeepSeek", "openai", base_url="https://api.deepseek.com",
        key_url="https://platform.deepseek.com/api_keys", env_key="DEEPSEEK_API_KEY",
        models=["deepseek-chat", "deepseek-reasoner", "deepseek-v4-pro"],
        note="Great-value reasoning models. OpenAI-compatible."),
    ProviderSpec(
        "groq", "Groq (fast LPU)", "openai", base_url="https://api.groq.com/openai/v1",
        key_url="https://console.groq.com/keys", env_key="GROQ_API_KEY",
        models=["llama-3.3-70b-versatile", "deepseek-r1-distill-llama-70b",
                "llama-3.1-8b-instant"],
        note="Extremely fast inference. OpenAI-compatible."),
    ProviderSpec(
        "openrouter", "OpenRouter (gateway to 100s of models)", "openai",
        base_url="https://openrouter.ai/api/v1", key_url="https://openrouter.ai/keys",
        env_key="OPENROUTER_API_KEY",
        models=["openrouter/auto", "anthropic/claude-3.5-sonnet",
                "google/gemini-2.0-flash-exp:free"],
        note="One key reaches OpenAI, Claude, Gemini, Llama, and free models."),
    ProviderSpec(
        "together", "Together AI", "openai", base_url="https://api.together.xyz/v1",
        key_url="https://api.together.ai/settings/api-keys", env_key="TOGETHER_API_KEY",
        models=["meta-llama/Llama-3.3-70B-Instruct-Turbo",
                "Qwen/Qwen2.5-72B-Instruct-Turbo"],
        note="Hosted open models. OpenAI-compatible."),
    ProviderSpec(
        "mistral", "Mistral", "openai", base_url="https://api.mistral.ai/v1",
        key_url="https://console.mistral.ai/api-keys", env_key="MISTRAL_API_KEY",
        models=["mistral-large-latest", "mistral-small-latest"],
        note="OpenAI-compatible."),
    ProviderSpec(
        "xai", "xAI (Grok)", "openai", base_url="https://api.x.ai/v1",
        key_url="https://x.ai/api", env_key="XAI_API_KEY",
        models=["grok-3", "grok-3-mini", "grok-2-latest"],
        note="OpenAI-compatible."),
    ProviderSpec(
        "google", "Google (Gemini)", "openai",
        base_url="https://generativelanguage.googleapis.com/v1beta/openai",
        key_url="https://aistudio.google.com/apikey", env_key="GEMINI_API_KEY",
        models=["gemini-2.0-flash", "gemini-2.5-pro", "gemini-1.5-flash"],
        note="Gemini via its OpenAI-compatible endpoint."),
    ProviderSpec(
        "perplexity", "Perplexity", "openai", base_url="https://api.perplexity.ai",
        key_url="https://www.perplexity.ai/settings/api", env_key="PERPLEXITY_API_KEY",
        models=["sonar-pro", "sonar", "llama-3.1-sonar-large-128k-online"],
        note="Models with live web access. OpenAI-compatible."),
    ProviderSpec(
        "lmstudio", "LM Studio (local)", "openai", base_url="http://localhost:1234/v1",
        needs_key=False, local=True, models=["local-model"],
        note="Runs GGUF models locally. Start its server first."),
    ProviderSpec(
        "vllm", "vLLM (local)", "openai", base_url="http://localhost:8000/v1",
        needs_key=False, local=True, models=["local-model"],
        note="High-throughput local inference server."),
    ProviderSpec(
        "robodaddy", "RoboDaddy (your trained model)", "openai",
        needs_key=False, local=True, models=[],
        note="Use a model you trained with `cyberspace robodaddy train/serve`."),
    ProviderSpec(
        "custom", "Custom (any OpenAI-compatible endpoint)", "openai",
        needs_key=False, models=[],
        note="Bring your own base URL + model name + optional key."),
]


_BY_KEY = {p.key: p for p in CATALOG}


def get_spec(key: str) -> ProviderSpec | None:
    """Look up a provider by its catalog key (case-insensitive)."""
    return _BY_KEY.get((key or "").lower())


def all_specs() -> list[ProviderSpec]:
    """Return the full ordered catalog."""
    return CATALOG


def resolve_choice(choice: str) -> ProviderSpec:
    """Resolve a menu choice (1-based number OR a provider key) to a spec."""
    choice = (choice or "").strip().lower()
    if choice.isdigit():
        idx = int(choice) - 1
        if 0 <= idx < len(CATALOG):
            return CATALOG[idx]
    spec = get_spec(choice)
    if spec is not None:
        return spec
    # Fuzzy: match on display text or key.
    for spec in CATALOG:
        if choice in spec.display.lower() or choice in spec.key:
            return spec
    return CATALOG[0]


def served_robodaddy_models() -> list[str]:
    """Names of RoboDaddy models that are trained+served and ready to use."""
    try:
        from ..config import MODULES_DIR
        reg = MODULES_DIR / "robodaddy" / "models.json"
        if not reg.exists():
            return []
        import json
        data = json.loads(reg.read_text())
        models = data if isinstance(data, list) else data.get("models", [])
        out = []
        for m in models:
            name = m.get("name") if isinstance(m, dict) else None
            status = m.get("status") if isinstance(m, dict) else None
            endpoint = m.get("endpoint") if isinstance(m, dict) else None
            if name and status == "served" and endpoint:
                out.append(name)
        return out
    except Exception:
        return []

