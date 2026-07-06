"""First-run agent setup wizard.

`cyberspace setup` walks a learner through choosing an LLM provider, model, and
connection - with visual prompts and sensible defaults. This MUST run before
the other platforms, because every module's agentic features depend on it.
"""
from __future__ import annotations

import typer
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.table import Table

from ..config import DEFAULT_OLLAMA_URL, SUGGESTED_MODELS
from .config import is_configured, load_config, save_config
from .llm import LLMConfig

console = Console()


def _banner() -> None:
    console.print(Panel.fit(
        "[bold cyan]cyberbot[/bold cyan] — agent setup\n"
        "[dim]Configure your personal pentest agent first. Every platform "
        "(IceBerg, AirBender, ShadowDragon, StickEm, RoboDaddy) plugs into this agent, "
        "so this step unlocks all agentic features.[/dim]",
        border_style="cyan",
    ))


def _check_ollama() -> bool:
    """Detect a running local Ollama (best option for learners / the Pi)."""
    import httpx
    try:
        r = httpx.get(f"{DEFAULT_OLLAMA_URL}/api/tags", timeout=2.0)
        return r.status_code == 200
    except Exception:
        return False


def _list_ollama_models() -> list[str]:
    import httpx
    try:
        r = httpx.get(f"{DEFAULT_OLLAMA_URL}/api/tags", timeout=3.0)
        return [m["name"] for m in r.json().get("models", [])]
    except Exception:
        return []


def run_wizard(force: bool = False) -> LLMConfig:
    if is_configured() and not force:
        cfg = load_config()
        console.print(f"[green]Agent already configured:[/green] "
                      f"{cfg.provider}/{cfg.model}")
        if not Confirm.ask("Reconfigure?", default=False):
            return cfg

    _banner()

    # 1) pick provider
    prov_table = Table("option", "provider", "best for")
    prov_table.add_row("1", "ollama", "local, offline, free (recommended for the Pi)")
    prov_table.add_row("2", "openai", "OpenAI API (gpt-4o-mini)")
    prov_table.add_row("3", "anthropic", "Claude API")
    prov_table.add_row("4", "custom", "any OpenAI-compatible endpoint")
    console.print(prov_table)

    choice = Prompt.ask("Choose provider", choices=["1", "2", "3", "4"], default="1")
    provider = {"1": "ollama", "2": "openai", "3": "anthropic", "4": "custom"}[choice]

    # 2) connection details
    base_url = DEFAULT_OLLAMA_URL
    api_key = ""
    model = ""

    if provider == "ollama":
        if _check_ollama():
            console.print("[green]Found a running Ollama.[/green]")
            models = _list_ollama_models()
            if models:
                console.print("Installed models: " + ", ".join(models))
                model = Prompt.ask("Model to use", default=models[0])
            else:
                console.print("[yellow]No models pulled yet.[/yellow] "
                              f"Try: ollama pull {SUGGESTED_MODELS['ollama'][0]}")
                model = Prompt.ask("Model name", default=SUGGESTED_MODELS["ollama"][0])
        else:
            console.print("[yellow]No Ollama detected on localhost:11434.[/yellow]")
            console.print("Install it free from https://ollama.com then re-run, "
                          "or point at a remote Ollama.")
            base_url = Prompt.ask("Ollama base URL", default=DEFAULT_OLLAMA_URL)
            model = Prompt.ask("Model name", default=SUGGESTED_MODELS["ollama"][0])
    else:
        base_url = Prompt.ask("API base URL (blank = provider default)",
                              default="")
        api_key = Prompt.ask("API key", password=True, default="")
        suggested = SUGGESTED_MODELS.get(provider, [])
        default_model = suggested[0] if suggested else ""
        model = Prompt.ask("Model name", default=default_model)

    # 3) persona (optional system prompt)
    sys_prompt = Prompt.ask(
        "Custom persona/system prompt (blank = default pentest assistant)",
        default="")

    cfg = LLMConfig(
        provider=provider, model=model, base_url=base_url,
        api_key=api_key, system_prompt=sys_prompt,
    )
    save_config(cfg)
    console.print(Panel.fit(
        f"[green]Agent configured.[/green]\n"
        f"provider: [bold]{provider}[/bold]   model: [bold]{model}[/bold]\n\n"
        f"[dim]Next: run `cyberspace agent` to chat, or `cyberspace iceberg/airbender/...`"
        f" for a platform. Tools register automatically once modules load.[/dim]",
        border_style="green",
    ))
    return cfg
