"""cyberspace main CLI.

Commands:
  cyberspace setup         configure the agent FIRST (unlocks agentic features)
  cyberspace agent         chat with the Cyberbot agent
  cyberspace dashboard     CyberPunked: unified view + one-AI control plane
  cyberspace modules       list loaded platforms
  cyberspace tools         list all agent tools
  cyberspace doctor        check what's installed / provisionable
  cyberspace iceberg|airbender|shadowdragon|stickem   each platform's CLI
"""
from __future__ import annotations

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from . import __version__
from .modules.base import LOADED_MODULES, TOOL_REGISTRY
from .modules.registry import discover_and_load
from .host import is_available

console = Console()
app = typer.Typer(
    help="cyberspace - an open-source agentic pentest platform.",
    no_args_is_help=True, rich_markup_mode="rich", add_completion=False,
)


def _autoload() -> None:
    if not LOADED_MODULES:
        discover_and_load()


@app.callback(invoke_without_command=True)
def _root(version: bool = typer.Option(False, "--version", "-V")):
    if version:
        console.print(f"cyberspace {__version__}")


@app.command()
def setup(force: bool = typer.Option(False, "--force", help="reconfigure")):
    """Configure the agent FIRST. Unlocks agentic features in all platforms."""
    from .agent.setup import run_wizard
    run_wizard(force=force)


@app.command()
def agent():
    """Chat with the cyberbot agent (all platform tools available)."""
    _autoload()
    from .agent.config import is_configured, load_config
    from .agent.core import Agent
    if not is_configured():
        console.print(Panel.fit(
            "[red]Agent not configured yet.[/red]\n"
            "Run [bold]cyberspace setup[/bold] first. The agent must be configured "
            "before other platforms gain agentic control.", border_style="red"))
        raise typer.Exit(1)
    cfg = load_config()
    a = Agent(cfg)
    console.print(Panel.fit(
        f"[bold cyan]cyberbot agent[/bold cyan] ({cfg.provider}/{cfg.model})\n"
        f"{len(TOOL_REGISTRY.all())} tools loaded. Type 'exit' to quit.",
        border_style="cyan"))
    from rich.prompt import Prompt
    while True:
        try:
            q = Prompt.ask("[cyan]you[/cyan]")
        except (EOFError, KeyboardInterrupt):
            break
        if q.strip().lower() in ("exit", "quit", "q"):
            break
        if q.strip():
            a.ask(q)


@app.command()
def dashboard():
    """CyberPunked: unified dashboard + one-AI control plane."""
    from .ui.dashboard import interactive
    interactive()


@app.command()
def modules():
    """List loaded platforms."""
    _autoload()
    t = Table("module", "platform", "tools", "description")
    for name, mod in sorted(LOADED_MODULES.items()):
        info = mod.describe()
        t.add_row(info.name, f"{info.emoji} {info.display_name}",
                  str(len(TOOL_REGISTRY.by_module(info.name))), info.description)
    console.print(t or "[dim]no modules loaded[/dim]")


@app.command()
def tools():
    """List all agent tools across all platforms."""
    _autoload()
    t = Table("tool", "module", "description")
    for tool in TOOL_REGISTRY.all():
        t.add_row(tool.name, tool.module, tool.description[:60])
    console.print(t or "[dim]no tools registered[/dim]")


@app.command()
def doctor():
    """Check what's installed and provisionable."""
    _autoload()
    from .agent.config import is_configured, load_config
    console.print(f"[bold]cyberspace {__version__} doctor[/bold]\n")
    t = Table("component", "status", "detail")
    cfg = load_config() if is_configured() else None
    t.add_row("agent", "[green]configured[/green]" if cfg else "[red]NOT configured[/red]",
              f"{cfg.provider}/{cfg.model}" if cfg else "run: cyberspace setup")
    for name, mod in sorted(LOADED_MODULES.items()):
        info = mod.describe()
        for ht in info.requires_tools:
            ok = is_available(ht) if ht not in ("pyserial", "playwright") else True
            t.add_row(f"{info.emoji} {info.display_name}/{ht}",
                      "[green]ok[/green]" if ok else "[red]missing[/red]",
                      "" if ok else f"install: apt install {ht} / pip install {ht}")
    console.print(t)
    console.print(f"\n[dim]{len(LOADED_MODULES)} platforms loaded, "
                  f"{len(TOOL_REGISTRY.all())} agent tools registered.[/dim]")
    if not is_configured():
        console.print("[yellow]→ Run `cyberspace setup` to configure the agent (recommended first).[/yellow]")


def _attach_platforms() -> None:
    """Register each loaded platform's CLI as a subcommand (idempotent)."""
    if getattr(app, "_cyberspace_attached", False):
        return
    _autoload()
    for name, mod in LOADED_MODULES.items():
        try:
            app.add_typer(mod.build_cli(), name=name, help=mod.describe().description)
        except Exception:
            pass
    app._cyberspace_attached = True


# Attach platforms on import so the `cyberspace` console script exposes them.
_attach_platforms()


if __name__ == "__main__":
    app()
