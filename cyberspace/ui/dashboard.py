"""cyberspace workspace driven by the seven-stage Cyber Kill Chain."""
from __future__ import annotations

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table

from ..modules.base import LOADED_MODULES, TOOL_REGISTRY

console = Console()

WORDMARK = r"""[bold green]
 ██████╗██╗   ██╗██████╗ ███████╗██████╗ ███████╗██████╗  █████╗  ██████╗███████╗
██╔════╝╚██╗ ██╔╝██╔══██╗██╔════╝██╔══██╗██╔════╝██╔══██╗██╔══██╗██╔════╝██╔════╝
██║      ╚████╔╝ ██████╔╝█████╗  ██████╔╝███████╗██████╔╝███████║██║     █████╗
██║       ╚██╔╝  ██╔══██╗██╔══╝  ██╔══██╗╚════██║██╔═══╝ ██╔══██║██║     ██╔══╝
╚██████╗   ██║   ██████╔╝███████╗██║  ██║███████║██║     ██║  ██║╚██████╗███████╗
 ╚═════╝   ╚═╝   ╚═════╝ ╚══════╝╚═╝  ╚═╝╚══════╝╚═╝     ╚═╝  ╚═╝ ╚═════╝╚══════╝[/bold green]"""


def banner() -> None:
    console.print(WORDMARK)
    console.print(Panel.fit(
        "[bold cyan]cyberspace[/bold cyan] - Cyber Kill Chain workspace\n"
        "[dim]Reconnaissance → Weaponization → Delivery → Exploitation → Installation →\n"
        "Command and Control (C2) → Actions on Objectives[/dim]",
        border_style="cyan"))


def show_team() -> None:
    from ..swarm import TEAM
    t = Table("stage", "objective", "platform tools")
    for a in TEAM:
        t.add_row(f"{a.emoji} {a.display}", a.role, ", ".join(a.tool_prefixes) or "(analysis)")
    console.print(t)


def _choose_workspace() -> bool:
    """Choose project/outcome logging or Ghost Mode on every launch."""
    from .. import projects
    active, items = projects.get_active(), projects.list_projects()
    console.print("\n[bold]Prompt library[/bold]")
    if active:
        console.print(f"  active project: [green]{active}[/green]")
    console.print("  1) Save prompts to active project\n  2) View/open a project folder")
    console.print("  3) Create a project folder\n"
                  "  4) Ghost Mode (no project copy or operation outcomes; Cyberdeck prompt ledger remains)")
    default = "1" if active else ("2" if items else "3")
    choice = Prompt.ask("Workspace mode", choices=["1", "2", "3", "4"], default=default)
    if choice == "4":
        console.print("[yellow]Ghost Mode: project copies and operation outcomes are disabled. "
                      "The ordered Cyberdeck prompt ledger is still saved.[/yellow]")
        return True
    if choice == "3":
        projects.create(Prompt.ask("New project name"), Prompt.ask("Description", default=""))
    elif choice == "2":
        if not items:
            projects.create(Prompt.ask("No projects yet. New project name"))
        else:
            for i, item in enumerate(items, 1):
                console.print(f"  {i}) {item['name']} ({item['prompt_count']} prompts) — {item['path']}")
            selected = Prompt.ask("Open project", default="1")
            try:
                projects.set_active(items[int(selected) - 1]["name"])
            except (ValueError, IndexError):
                if not projects.find_and_open(selected):
                    console.print(f"[red]No project matching '{selected}'.[/red]")
                    return _choose_workspace()
    elif not active:
        projects.create(Prompt.ask("Project name"))
    console.print(f"[green]Saving to:[/green] {projects.get_active()}")
    return False


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
            "[red]No AI provider configured.[/red]\n\n"
            "The swarm needs an LLM to think. Connect one first:\n"
            "  [cyan]cyberspace setup[/cyan]\n\n"
            "[dim]Pick a provider (local Ollama, OpenAI, Claude, z.ai, DeepSeek, "
            "Groq, Gemini, ...) - it only takes a key.[/dim]",
            border_style="red"))
        return
    cfg = load_config()
    try:
        swarm = Swarm(cfg, console, ghost_mode=_choose_workspace())
    except Exception as e:
        console.print(Panel.fit(
            f"[red]Could not start the swarm:[/red] {e}\n\n"
            "[dim]Run `cyberspace setup --force` to reconfigure the AI provider.[/dim]",
            border_style="red"))
        return
    console.print(Panel.fit(
        f"[bold magenta]Cyber Kill Chain[/bold magenta] ({cfg.provider}/{cfg.model})\n"
        "Seven chronological stages are active; execution and model failover are shown live.\n"
        "Type 'exit' to leave.", border_style="magenta"))
    console.print("[dim]Example: 'Scan 10.10.10.0/24, find the web app, test it, write a report.'[/dim]\n")
    while True:
        try:
            q = Prompt.ask("[bold green]cyberspace[/bold green] [magenta]objective[/magenta]")
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
            "[red]No AI provider configured.[/red]\n\n"
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
        console.print("  1) Show Kill Chain      2) Show platforms + tools")
        console.print("  3) Open a platform      4) [bold magenta]Swarm mode[/bold magenta] (run the Kill Chain)")
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
