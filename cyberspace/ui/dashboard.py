"""cyberspace dashboard - the multi-agent swarm hub.

The tandem-style control plane: one clean space where you command a TEAM of
specialized sub-agents. The Orchestrator delegates to Recon, Exploit, Ghost,
Hardware, Smith, or Scribe automatically based on your objective.
"""
from __future__ import annotations

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table

from ..modules.base import LOADED_MODULES, TOOL_REGISTRY

console = Console()


def banner() -> None:
    console.print(Panel.fit(
        "[bold cyan]cyberspace[/bold cyan] - multi-agent command hub\n"
        "[dim]Command a swarm of specialized agents from one space. The Orchestrator\n"
        "delegates to the right specialist for each phase of your engagement.[/dim]",
        border_style="cyan"))


def show_team() -> None:
    from ..swarm import TEAM
    t = Table("agent", "role", "specialty")
    for a in TEAM:
        t.add_row(f"{a.emoji} {a.display}", a.role, ", ".join(a.tool_prefixes) or "(analysis)")
    console.print(t)


def show_modules() -> None:
    t = Table("module", "platform", "tools", "description")
    for name, mod in sorted(LOADED_MODULES.items()):
        info = mod.describe()
        t.add_row(info.name, f"{info.emoji} {info.display_name}",
                  str(len(TOOL_REGISTRY.by_module(info.name))), info.description)
    console.print(t)


def run_swarm() -> None:
    from ..agent.config import is_configured, load_config
    from ..swarm import Swarm
    if not is_configured():
        console.print("[red]Agent not configured.[/red] Run: cyberspace setup"); return
    cfg = load_config()
    swarm = Swarm(cfg, console)
    console.print(Panel.fit(
        f"[bold magenta]Swarm mode[/bold magenta] ({cfg.provider}/{cfg.model})\n"
        "The Orchestrator delegates to: Recon, Exploit, Ghost, Hardware, Smith, Scribe.\n"
        "Type 'exit' to leave.", border_style="magenta"))
    console.print("[dim]Example: 'Scan 10.10.10.0/24, find the web app, test it, write a report.'[/dim]\n")
    while True:
        try:
            q = Prompt.ask("[magenta]mission[/magenta]")
        except (EOFError, KeyboardInterrupt):
            break
        if q.strip().lower() in ("exit", "quit", "q"):
            break
        if q.strip():
            swarm.ask(q)


def run_single_agent() -> None:
    from ..agent.config import is_configured, load_config
    from ..agent.core import Agent
    if not is_configured():
        console.print("[red]Agent not configured.[/red] Run: cyberspace setup"); return
    cfg = load_config()
    a = Agent(cfg, console=console)
    console.print(Panel.fit(
        f"[bold cyan]Single-agent[/bold cyan] ({cfg.provider}/{cfg.model})\n"
        f"{len(TOOL_REGISTRY.all())} tools across {len(LOADED_MODULES)} platforms.",
        border_style="cyan"))
    while True:
        try:
            q = Prompt.ask("[cyan]you[/cyan]")
        except (EOFError, KeyboardInterrupt):
            break
        if q.strip().lower() in ("exit", "quit", "q"):
            break
        if q.strip():
            a.ask(q)


def interactive() -> None:
    from ..modules.registry import discover_and_load
    discover_and_load()
    banner()
    while True:
        console.print("\n[bold]cyberspace menu[/bold]")
        console.print("  1) Show agent team      2) Show platforms + tools")
        console.print("  3) Open a platform      4) [bold magenta]Swarm mode[/bold magenta] (command the whole team)")
        console.print("  5) Single-agent chat    q) quit")
        choice = Prompt.ask("Choice", default="4")
        if choice == "1": show_team()
        elif choice == "2": show_modules()
        elif choice == "3":
            show_modules()
            name = Prompt.ask("Platform name")
            mod = LOADED_MODULES.get(name)
            if not mod:
                console.print(f"[red]no module '{name}'[/red]"); continue
            console.print(f"[yellow]Spawning `cyberspace {name} --help`[/yellow]")
            import subprocess, sys
            subprocess.run([sys.executable, "-m", "cyberspace", name, "--help"])
        elif choice == "4": run_swarm()
        elif choice == "5": run_single_agent()
        elif choice.lower() == "q": break
