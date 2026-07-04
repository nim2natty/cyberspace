"""CyberPunked - the unified dashboard / one-AI control plane.

Two modes:
  - Interactive menu: see all modules + their tools, launch any CLI directly.
  - Unified AI: one conversation where the cyberbot agent can call ANY tool
    across ALL modules (IceBerg + AirBender + ShadowDragon + StickEm).

This is `cyberspace dashboard` (a.k.a CyberPunked).
"""
from __future__ import annotations

import typer
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table

from ..modules.base import LOADED_MODULES, TOOL_REGISTRY

console = Console()


def banner() -> None:
    console.print(Panel.fit(
        "[bold cyan]CYBERPUNKED[/bold cyan] — unified dashboard\n"
        "[dim]All platforms in one place. Drive any tool directly, or chat with one "
        "AI that commands every platform.[/dim]",
        border_style="cyan",
    ))


def show_modules() -> None:
    t = Table("module", "platform", "tools", "description")
    for name, mod in sorted(LOADED_MODULES.items()):
        info = mod.describe()
        n_tools = len(TOOL_REGISTRY.by_module(info.name))
        t.add_row(info.name, f"{info.emoji} {info.display_name}",
                  str(n_tools), info.description)
    console.print(t)


def show_tools() -> None:
    t = Table("tool", "module", "description")
    for tool in TOOL_REGISTRY.all():
        t.add_row(tool.name, tool.module, tool.description[:50])
    console.print(t)


def interactive() -> None:
    """Menu: open a platform's CLI, list tools, or enter the unified AI."""
    from ..modules.registry import discover_and_load
    discover_and_load()
    banner()
    while True:
        console.print("\n[bold]CyberPunked menu[/bold]")
        console.print("  1) Show platforms      2) Show all agent tools")
        console.print("  3) Open a platform     4) Unified AI (all tools)")
        console.print("  q) quit")
        choice = Prompt.ask("Choice", default="1")
        if choice == "1":
            show_modules()
        elif choice == "2":
            show_tools()
        elif choice == "3":
            show_modules()
            name = Prompt.ask("Platform name")
            mod = LOADED_MODULES.get(name)
            if not mod:
                console.print(f"[red]no module '{name}'[/red]"); continue
            console.print(f"[yellow]Spawning `cyberspace {name} --help`[/yellow]")
            import subprocess, sys
            subprocess.run([sys.executable, "-m", "cyberspace", name, "--help"])
        elif choice == "4":
            run_unified_ai()
        elif choice.lower() == "q":
            break


def run_unified_ai() -> None:
    """One AI conversation with every module's tools available."""
    from ..agent.config import is_configured, load_config
    from ..agent.core import Agent
    if not is_configured():
        console.print("[red]Agent not configured.[/red] Run: cyberspace setup")
        return
    cfg = load_config()
    agent = Agent(cfg)
    console.print(Panel.fit(
        f"[bold]Unified AI[/bold] ({cfg.provider}/{cfg.model})\n"
        f"{len(TOOL_REGISTRY.all())} tools across "
        f"{len(LOADED_MODULES)} platforms available. Type 'exit' to leave.",
        border_style="magenta"))
    console.print("[dim]Example: 'Scan my lab 10.10.10.0/24, then identify the "
                  "web app, then launch IceBerg to browse it.'[/dim]\n")
    while True:
        try:
            q = Prompt.ask("[magenta]you[/magenta]")
        except (EOFError, KeyboardInterrupt):
            break
        if q.strip().lower() in ("exit", "quit", "q"):
            break
        if q.strip():
            agent.ask(q)
