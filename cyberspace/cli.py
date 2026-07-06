"""cyberspace main CLI.

Commands:
  cyberspace setup         configure the agent FIRST (unlocks agentic features)
  cyberspace agent         chat with the cyberbot agent
  cyberspace dashboard     unified view + one-AI control plane
  cyberspace memory        view/modify the learned operator profile
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
    """The multi-agent swarm hub (default). Command the whole team from one space."""
    from .ui.dashboard import interactive
    interactive()


@app.command()
def swarm(roe: str = typer.Option("", "--roe", help="path to a Rules of Engagement .md file")):
    """Launch the multi-agent swarm directly. The Orchestrator commands the team."""
    from .ui.dashboard import run_swarm
    if roe:
        from pathlib import Path
        p = Path(roe)
        if p.exists():
            console.print(f"[dim]loaded RoE from {roe}[/dim]")
            from . import memory
            memory.semantic_fact("roe_file", str(p))
    run_swarm()


@app.command()
def quickstart():
    """One-command guided first run: configure agent, then launch the swarm."""
    console.print(Panel.fit(
        "[bold cyan]cyberspace quickstart[/bold cyan]\n"
        "[dim]Let's get you running in 60 seconds.[/dim]", border_style="cyan"))
    from .agent.config import is_configured
    if not is_configured():
        console.print("[yellow]Step 1:[/yellow] configure the agent (needed first).")
        from .agent.setup import run_wizard
        run_wizard(force=True)
    else:
        console.print("[green]Agent already configured. Skipping to the swarm.[/green]")
    console.print("\n[yellow]Step 2:[/yellow] launch the multi-agent swarm.")
    from .ui.dashboard import run_swarm
    run_swarm()


@app.command()
def report(outfile: str = typer.Option("engagement_report.md", "--out", "-o")):
    """Generate a markdown engagement report from memory + activity history."""
    from . import memory as mem
    from pathlib import Path
    episodes = mem.recent_episodes(100)
    profile = mem.load_profile()
    lines = ["# Engagement Report", "", f"Generated: {__import__('datetime').datetime.now().isoformat()}", ""]
    lines.append(f"## Operator profile\nSkill: {profile.skill_level}; "
                 f"tools used: {', '.join(profile.preferred_tools[:8]) or 'none'}")
    lines.append(f"\n## Activity log ({len(episodes)} actions)\n")
    lines.append("| time | agent | action | result |")
    lines.append("|------|-------|--------|--------|")
    for ep in episodes:
        lines.append(f"| {ep.get('ts','')[:19]} | {ep.get('platform','')} | "
                     f"{ep.get('action','')} | {ep.get('result_summary','')[:60].replace('|','/')} |")
    Path(outfile).write_text("\n".join(lines))
    console.print(f"[green]Report written to[/green] {outfile} ({len(episodes)} actions)")


@app.command()
def memory(action: str = typer.Argument("show", help="show|skill|note|recall|recent"),
           value: str = typer.Argument("", help="value for skill/note/recall/recent")):
    """View/modify the learned operator profile (personalization memory)."""
    from . import memory as mem
    if action == "show":
        console.print(Panel.fit(mem.context_block(), title="operator profile + memory",
                                border_style="magenta"))
    elif action == "skill" and value:
        mem.set_skill_level(value)
        console.print(f"[green]skill level set to[/green] {value}")
    elif action == "note" and value:
        mem.add_note(value)
        console.print(f"[green]note saved:[/green] {value}")
    elif action == "recall" and value:
        for ep in mem.recall(value):
            console.print(f"[dim]{ep.get('ts','')[:19]}[/dim] {ep.get('platform','')}: "
                          f"{ep.get('action','')} -> {ep.get('result_summary','')[:80]}")
    elif action == "recent":
        for ep in mem.recent_episodes(int(value) if value else 10):
            console.print(f"[dim]{ep.get('ts','')[:19]}[/dim] {ep.get('platform','')}: "
                          f"{ep.get('action','')}")
    elif action == "tools":
        for tool, count in mem.top_tools(10):
            console.print(f"  {tool}: {count}x")
    else:
        console.print("[dim]usage: cyberspace memory show|skill <level>|note <text>|"
                      "recall <query>|recent [N]|tools[/dim]")


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
