"""First-run agent setup wizard.

`cyberspace setup` walks a learner through choosing an LLM provider, model, and
connection - with visual prompts and sensible defaults. This MUST run before
the other platforms, because every module's agentic features depend on it.
"""
from __future__ import annotations

import os

import typer
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.table import Table

from .config import is_configured, load_config, save_config
from .llm import LLMConfig, ProviderError, get_provider
from .providers import (
    DEFAULT_OLLAMA_URL,
    all_specs,
    resolve_choice,
    served_robodaddy_models,
)

console = Console()


def _banner() -> None:
    console.print(Panel.fit(
        "[bold cyan]cyberspace[/bold cyan] - connect your AI brain\n"
        "[dim]Pick any LLM (local, OpenAI, Claude, z.ai, DeepSeek, Groq, "
        "Gemini, a model you trained, ...) and we'll wire it up. Every platform "
        "(IceBerg, AirBender, ShadowDragon, StickEm, RoboDaddy) plugs into this.[/dim]",
        border_style="cyan",
    ))


def _check_ollama(base_url: str) -> bool:
    import httpx
    try:
        r = httpx.get(f"{base_url}/api/tags", timeout=2.0)
        return r.status_code == 200
    except Exception:
        return False


def _list_ollama_models(base_url: str) -> list[str]:
    import httpx
    try:
        r = httpx.get(f"{base_url}/api/tags", timeout=3.0)
        return [m["name"] for m in r.json().get("models", [])]
    except Exception:
        return []


def _discover_models(spec, base_url: str, api_key: str) -> list[str]:
    """Ask the configured provider for its current model IDs."""
    if spec.api_style == "ollama":
        return _list_ollama_models(base_url)
    if not base_url:
        return []
    import httpx
    if spec.api_style == "anthropic":
        headers = {"x-api-key": api_key, "anthropic-version": "2023-06-01"}
        url = "https://api.anthropic.com/v1/models"
    else:
        headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        url = f"{base_url.rstrip('/')}/models"
    try:
        response = httpx.get(url, headers=headers, timeout=10.0)
        response.raise_for_status()
        return sorted({str(item["id"]) for item in response.json().get("data", []) if item.get("id")})
    except Exception:
        return []


def _gather_ollama(spec) -> tuple[str, str, str]:
    """Returns (base_url, api_key, model) for Ollama."""
    base_url = spec.base_url
    if _check_ollama(base_url):
        console.print(f"[green]Found a running Ollama at {base_url}.[/green]")
        models = _list_ollama_models(base_url)
        if models:
            model = _pick_model(models, default=models[0], label="model")
        else:
            console.print(f"[yellow]No models pulled yet.[/yellow] Try: ollama pull {spec.models[0]}")
            model = _pick_model(spec.models, default=spec.models[0], label="model")
    else:
        console.print(f"[yellow]No Ollama detected at {base_url}.[/yellow]")
        console.print("Install it free from https://ollama.com then re-run, or point at a remote one.")
        base_url = Prompt.ask("Ollama base URL", default=base_url)
        model = _pick_model(spec.models, default=spec.models[0], label="model")
    return base_url, "", model


def _gather_robodaddy() -> tuple[str, str, str] | None:
    """Returns (endpoint, api_key, model) for a served RoboDaddy model, or None."""
    served = served_robodaddy_models()
    if not served:
        console.print("[yellow]No served RoboDaddy models found.[/yellow]")
        console.print("Train and serve one first: cyberspace robodaddy train <use-case> "
                      "&& cyberspace robodaddy serve <name>")
        return None
    console.print("Served models: " + ", ".join(served))
    model = Prompt.ask("Model to use", default=served[0])
    from ..platforms.robodaddy.serve import use_as_cyberbot
    endpoint, api_key = use_as_cyberbot(model)
    return endpoint, api_key, model


def _pick_model(options: list[str], *, default: str = "", label: str = "model") -> str:
    """Numbered model picker. The user picks a number, or types a custom name.

    So you never have to type out a full model string - just press Enter for the
    default or type the number next to the model you want.
    """
    if not options:
        return Prompt.ask(f"{label} name", default=default)
    console.print(f"Pick a {label} (enter the number, or type a custom name):")
    for i, m in enumerate(options, 1):
        console.print(f"  [cyan]{i}[/cyan]) {m}")
    choice = Prompt.ask(f"{label.capitalize()}", default="1")
    if choice.strip().isdigit():
        idx = int(choice) - 1
        if 0 <= idx < len(options):
            return options[idx]
    return choice.strip() or (options[0] if options else default)


def run_wizard(force: bool = False) -> LLMConfig:
    if is_configured() and not force:
        cfg = load_config()
        console.print(f"[green]AI already connected:[/green] {cfg.provider}/{cfg.model}")
        if not Confirm.ask("Reconfigure?", default=False):
            return cfg

    _banner()

    # 1) pick provider from the catalog
    t = Table("#", "provider", "key?", "best for", title="Available LLMs")
    for i, spec in enumerate(all_specs(), 1):
        keycol = "no" if not spec.needs_key else "yes"
        t.add_row(str(i), spec.display, keycol, spec.note)
    console.print(t)

    spec = None
    while spec is None:
        choice = Prompt.ask("Pick a provider (number or name)", default="1")
        spec = resolve_choice(choice)
        if spec is None:
            console.print("[red]Unknown provider. Choose a number or exact provider name above.[/red]")
    console.print(f"[green]Selected:[/green] {spec.display}")

    # 2) gather connection details per provider
    api_key = ""
    model = spec.models[0] if spec.models else ""
    base_url = spec.base_url

    if spec.key == "ollama":
        base_url, api_key, model = _gather_ollama(spec)
    elif spec.key == "robodaddy":
        got = _gather_robodaddy()
        if got is None:
            console.print("[red]No RoboDaddy model selected.[/red] Re-run setup and pick another provider.")
            raise typer.Exit(1)
        base_url, api_key, model = got
    elif spec.key == "custom":
        base_url = Prompt.ask("Base URL (OpenAI-compatible /chat/completions base)",
                              default="http://localhost:8000/v1")
        model = Prompt.ask("Model name", default="local-model")
        api_key = Prompt.ask("API key (blank = none)", password=True, default="")
    else:
        # Cloud provider from the catalog: env var first, then prompt for the key.
        env_val = os.environ.get(spec.env_key, "") if spec.env_key else ""
        if env_val:
            console.print(f"[green]Found an API key in ${spec.env_key}.[/green]")
            api_key = env_val
        else:
            if spec.key_url:
                console.print(f"[dim]Get a key: {spec.key_url}[/dim]")
            api_key = Prompt.ask("API key", password=True, default="")
        if not spec.local:
            base_url = Prompt.ask("Base URL (blank = provider default)", default=spec.base_url)
        discovered = _discover_models(spec, base_url, api_key)
        if discovered:
            console.print(f"[green]Loaded {len(discovered)} current models from {spec.display}.[/green]")
        else:
            console.print("[dim]Live model discovery unavailable; showing reviewed fallbacks. "
                          "You can type any exact model ID.[/dim]")
        options = discovered or spec.models
        model = _pick_model(options, default=options[0] if options else "", label="model")

    # 3) persona (optional system prompt)
    sys_prompt = Prompt.ask(
        "Custom persona/system prompt (blank = default pentest assistant)",
        default="")

    cfg = LLMConfig(
        provider=spec.key, model=model, base_url=base_url,
        api_key=api_key, system_prompt=sys_prompt,
    )

    # 4) quick connectivity test (one tiny request). Failures are non-fatal.
    if Confirm.ask("Test the connection now?", default=True):
        try:
            prov = get_provider(cfg)
            prov.chat([{"role": "user", "content": "Reply with the single word: ok"}], [])
            console.print("[green]Connection OK.[/green]")
        except ProviderError as e:
            console.print(Panel.fit(
                f"[red]Connection check failed:[/red]\n{e}\n\n"
                "[dim]The config is still saved. Fix the issue above and re-run "
                "`cyberspace setup`, or answer 'no' to skip the test.[/dim]",
                border_style="red"))
        except Exception as e:  # last-resort: keep it readable
            console.print(f"[yellow]Could not verify the connection: {e}[/yellow]")

    try:
        key_storage = save_config(cfg)
    except Exception as exc:
        console.print(Panel.fit(
            f"[red]The API key was not saved:[/red] {exc}\n\n"
            "Install/unlock your system credential store, or set the provider's API-key "
            "environment variable. Cyberspace will not write API keys to plaintext files.",
            border_style="red"))
        raise typer.Exit(1)
    console.print(Panel.fit(
        f"[green]AI connected.[/green]\n"
        f"provider: [bold]{spec.key}[/bold]   model: [bold]{model}[/bold]\n"
        f"credentials: [bold]{key_storage}[/bold]\n\n"
        "[dim]Next: `cyberspace swarm` to command the team, or `cyberspace agent` "
        "for a single chat. Tools register automatically.[/dim]",
        border_style="green"))
    return cfg
