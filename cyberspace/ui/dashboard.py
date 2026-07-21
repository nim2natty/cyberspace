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
    from ..agent.llm import ProviderError
    from ..swarm import Swarm
    if not is_configured():
        console.print(Panel.fit(
            "[red]No AI brain connected yet.[/red]\n\n"
            "The swarm needs an LLM to think. Connect one first:\n"
            "  [cyan]cyberspace setup[/cyan]\n\n"
            "[dim]Pick any provider (local Ollama, OpenAI, Claude, z.ai, DeepSeek, "
            "Groq, Gemini, ...) - it only takes a key.[/dim]",
            border_style="red"))
        return
    cfg = load_config()
    try:
        swarm = Swarm(cfg, console)
    except Exception as e:
        console.print(Panel.fit(
            f"[red]Could not start the swarm:[/red] {e}\n\n"
            "[dim]Run `cyberspace setup --force` to reconfigure your AI brain.[/dim]",
            border_style="red"))
        return
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
            try:
                swarm.ask(q)
            except ProviderError as e:
                console.print(Panel.fit(
                    f"[red]The AI couldn't respond:[/red]\n{e}\n\n"
                    "[dim]Fix the issue above (e.g. bad API key, wrong model, or the "
                    "service is down) and try again. Run `cyberspace setup` to "
                    "reconfigure.[/dim]", border_style="red"))
            except KeyboardInterrupt:
                console.print("[dim](interrupted)[/dim]")


def run_single_agent() -> None:
    from ..agent.config import is_configured, load_config
    from ..agent.core import Agent
    from ..agent.llm import ProviderError
    if not is_configured():
        console.print(Panel.fit(
            "[red]No AI brain connected yet.[/red]\n\n"
            "Run [cyan]cyberspace setup[/cyan] to connect an LLM first.",
            border_style="red"))
        return
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
            try:
                a.ask(q)
            except ProviderError as e:
                console.print(Panel.fit(
                    f"[red]The AI couldn't respond:[/red]\n{e}\n\n"
                    "[dim]Check your API key / model / network. Run `cyberspace setup` "
                    "to reconfigure.[/dim]", border_style="red"))
            except KeyboardInterrupt:
                console.print("[dim](interrupted)[/dim]")


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
