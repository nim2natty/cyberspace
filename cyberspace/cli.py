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
    help="cyberspace - authorized security tools, scoped AI modes, and model-training commands.",
    no_args_is_help=False, rich_markup_mode="rich", add_completion=False,
)


def _autoload() -> None:
    if not LOADED_MODULES:
        discover_and_load()


@app.callback(invoke_without_command=True)
def _root(
    ctx: typer.Context,
    version: bool = typer.Option(False, "--version", "-V"),
    elevated: bool = typer.Option(
        False, "--elevated", help="confirm elevation for allowlisted network/capture tools"),
):
    if version:
        console.print(f"cyberspace {__version__}")
        raise typer.Exit()
    if elevated:
        from rich.prompt import Confirm
        from .host import enable_elevation, runtime_summary
        ok, message = enable_elevation(
            confirm=lambda prompt: Confirm.ask(prompt, default=False, console=console))
        console.print(("[green]" if ok else "[red]") + message)
        console.print(f"[dim]{runtime_summary()}[/dim]")
        if not ok:
            raise typer.Exit(1)
    if ctx.invoked_subcommand is None:
        from .ui.dashboard import interactive
        interactive()


@app.command()
def setup(force: bool = typer.Option(False, "--force", help="reconfigure")):
    """Configure the agent FIRST. Unlocks agentic features in all platforms."""
    from .agent.setup import run_wizard
    run_wizard(force=force)


@app.command()
def update(
    yes: bool = typer.Option(False, "--yes", "-y", help="confirm the update non-interactively"),
    force: bool = typer.Option(False, "--force", help="attempt update with local source changes"),
):
    """Update Cyberspace to the latest version using the current install method."""
    from pathlib import Path
    from rich.prompt import Confirm
    from .updater import installation_method, update_latest
    root = Path(__import__("os").environ.get(
        "CYBERSPACE_ROOT", Path(__file__).resolve().parents[1]))
    method = installation_method(root)
    console.print(f"[cyan]Update method:[/cyan] {method}")
    if not yes and not Confirm.ask("Update Cyberspace to the latest version?", default=False,
                                   console=console):
        console.print("[dim]Update cancelled.[/dim]")
        return
    result = update_latest(root=root, force=force)
    console.print(("[green]" if result.ok else "[red]") + result.message)
    if not result.ok:
        raise typer.Exit(1)


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


@app.command("ai")
def platform_ai(
    platform: str = typer.Argument(..., help="iceberg|airbender|shadowdragon|stickem|robodaddy"),
    request: list[str] = typer.Argument(..., help="plain-language request for that platform"),
):
    """Run one platform in scoped AI mode (example: `cyberspace ai iceberg check privacy`)."""
    _autoload()
    selector = platform.strip().lower()
    platform = selector.split(".", 1)[0]
    if platform not in LOADED_MODULES:
        console.print(f"[red]Unknown platform '{platform}'.[/red] Choose: " +
                      ", ".join(sorted(LOADED_MODULES)))
        raise typer.Exit(2)
    from .agent.config import load_config
    from .agent.core import Agent
    cfg = load_config()
    if not cfg:
        console.print("[red]AI is not configured.[/red] Run: cyberspace setup")
        raise typer.Exit(1)
    scoped = TOOL_REGISTRY.scoped(platform)
    if "." in selector:
        selected = scoped.get(selector)
        if not selected:
            console.print(f"[red]Unknown tool '{selector}'.[/red] Available: " +
                          ", ".join(tool.name for tool in scoped.all()))
            raise typer.Exit(2)
        from .modules.base import ToolRegistry
        exact = ToolRegistry()
        exact.register(selected)
        scoped = exact
    prompt = " ".join(request).strip()
    console.print(Panel.fit(
        f"[bold cyan]{selector} AI mode[/bold cyan] ({cfg.provider}/{cfg.model})\n"
        f"Runtime scope: {len(scoped.all())} selected tool(s) only.", border_style="cyan"))
    Agent(cfg, registry=scoped, console=console, include_project_tools=False,
          scope=selector).ask(prompt)


@app.command()
def dashboard():
    """Open the Cyber Kill Chain workspace (the default `cyberspace` view)."""
    from .ui.dashboard import interactive
    interactive()


@app.command()
def swarm(roe: str = typer.Option("", "--roe", help="path to a Rules of Engagement .md file")):
    """Launch the seven-stage Cyber Kill Chain workspace directly."""
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
    console.print("\n[yellow]Step 2:[/yellow] launch the Cyber Kill Chain workspace.")
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


# --- projects: named workspaces that save every prompt ---------------------
project_app = typer.Typer(help="Projects: named workspaces that save every prompt you send.")
app.add_typer(project_app, name="project")


@project_app.command("create")
def project_create(name: str = typer.Argument(..., help="project name, e.g. 'surveillance in chicago'"),
                   description: str = typer.Option("", "--desc", "-d")):
    """Create a new project and make it the active one."""
    from . import projects
    pdir = projects.create(name, description=description)
    console.print(f"[green]Created and activated project:[/green] {name}")
    console.print(f"[dim]Folder: {pdir}[/dim]")
    console.print(f"[dim]Every prompt you send to the AI will now be saved here.[/dim]")


@project_app.command("list")
def project_list():
    """Show all your projects and how many prompts each has."""
    from . import projects
    active = projects.get_active()
    projs = projects.list_projects()
    if not projs:
        console.print("[dim]No projects yet. Create one: cyberspace project create \"my project\"[/dim]")
        return
    t = Table("project", "prompts", "created", "active")
    for p in projs:
        mark = "[green]*[/green]" if p["name"] == active else ""
        t.add_row(p["name"], str(p.get("prompt_count", 0)),
                  p.get("created", "")[:10], mark)
    console.print(t)
    if active:
        console.print(f"\n[dim]* = active project (prompts are being saved to '{active}')[/dim]")


@project_app.command("open")
def project_open(name: str = typer.Argument(..., help="project name to open")):
    """Open a project — set it active AND show all saved prompts."""
    from . import projects
    p = projects.get(name)
    if not p:
        console.print(f"[red]No project named '{name}'.[/red] Run: cyberspace project list")
        raise typer.Exit(1)
    projects.set_active(p["name"])
    console.print(f"[green]Opened project:[/green] {p['name']}")
    if p.get("description"):
        console.print(f"[dim]{p['description']}[/dim]")
    console.print(f"[dim]New prompts will be saved here.[/dim]\n")
    prompts = projects.get_prompts(p["name"])
    if not prompts:
        console.print("[yellow]No prompts saved yet. Start using the AI and they'll appear here.[/yellow]")
        return
    console.print(f"[bold]Saved prompts ({len(prompts)}):[/bold]\n")
    for i, entry in enumerate(prompts, 1):
        ts = entry.get("ts", "")[:19]
        console.print(f"[dim]{ts}[/dim]  [cyan]#{i}[/cyan]")
        console.print(f"  [bold]you:[/bold] {entry.get('prompt', '')[:200]}")
        resp = entry.get("response", "")
        if resp:
            console.print(f"  [dim]AI: {resp[:200]}...[/dim]" if len(resp) > 200 else f"  [dim]AI: {resp}[/dim]")
        console.print()


@project_app.command("use")
def project_use(name: str = typer.Argument(..., help="project to set as active (saves future prompts)")):
    """Set a project as active without showing its prompts."""
    from . import projects
    p = projects.get(name)
    if not p:
        console.print(f"[red]No project named '{name}'.[/red]"); raise typer.Exit(1)
    projects.set_active(p["name"])
    console.print(f"[green]Active project:[/green] {p['name']}")
    console.print(f"[dim]Every prompt you send to the AI will be saved here.[/dim]")


@project_app.command("close")
def project_close():
    """Stop writing project prompt copies; Cyberdeck ledger remains enabled."""
    from . import projects
    projects.set_active(None)
    console.print("[dim]No active project. Project prompt copies are disabled; "
                  "Cyberdeck continues to store the ordered prompt ledger.[/dim]")


@project_app.command("delete")
def project_delete(name: str = typer.Argument(...)):
    """Delete a project folder; global Cyberdeck prompt records are retained."""
    from . import projects
    if projects.delete(name):
        console.print(f"[green]Deleted project folder and its project prompt copies:[/green] {name}\n"
                      "[dim]Global Cyberdeck prompt records are retained.[/dim]")
    else:
        console.print(f"[red]No project named '{name}'.[/red]")


@project_app.command("status")
def project_status():
    """Show which project is active (if any)."""
    from . import projects
    active = projects.get_active()
    if active:
        console.print(f"[green]Active project:[/green] {active}")
        prompts = projects.get_prompts(active)
        console.print(f"[dim]{len(prompts)} prompts saved.[/dim]")
    else:
        console.print("[dim]No active project. Create one: cyberspace project create \"my project\"[/dim]")


@project_app.command("search")
def project_search(query: str = typer.Argument(..., help="keyword to search for in project names and saved chats")):
    """Search all projects and saved chats by keyword."""
    from . import projects
    results = projects.search(query)
    if not results:
        console.print(f"[yellow]No results for '{query}'.[/yellow]")
        return
    console.print(f"[bold]Found {len(results)} match(es) for '{query}':[/bold]\n")
    for r in results:
        rtype = r.get("type", "")
        icon = "📁" if rtype == "project" else "💬"
        console.print(f"{icon} [bold]{r.get('name', '')}[/bold] [dim]({r.get('matched', '')})[/dim]")
        snippet = r.get("snippet", "")
        if snippet:
            console.print(f"   [dim]{snippet[:100]}[/dim]")
        if r.get("ts"):
            console.print(f"   [dim]saved: {r['ts']}[/dim]")
        console.print()


@app.command()
def providers():
    """List every LLM provider cyberspace can connect to.

    Shows the catalog of agentic LLMs (local + cloud) with their API dialect,
    where to get a key, and suggested models. Use `cyberspace setup` to connect one.
    """
    from .agent.providers import all_specs
    from .agent.config import load_config
    cfg = load_config()
    active = cfg.provider if cfg else None
    t = Table("#", "provider", "style", "key?", "suggested models", "")
    for i, spec in enumerate(all_specs(), 1):
        style = {"ollama": "ollama", "openai": "openai-compat", "anthropic": "anthropic"}.get(spec.api_style, spec.api_style)
        keycol = "no" if not spec.needs_key else "yes"
        models = ", ".join(spec.models[:3]) + (" ..." if len(spec.models) > 3 else "")
        mark = "[green]<- active[/green]" if active == spec.key else ""
        t.add_row(str(i), spec.display, style, keycol, models, mark)
    console.print(t)
    console.print("\n[dim]Connect one with: cyberspace setup[/dim]")


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
    from .host import runtime_environment, runtime_summary
    console.print(f"[bold]cyberspace {__version__} doctor[/bold]\n")
    t = Table("component", "status", "detail")
    runtime = runtime_environment()
    t.add_row("execution environment",
              "[yellow]container[/yellow]" if runtime["container"] else "[green]native host[/green]",
              runtime_summary())
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


@app.command()
def uninstall(
    remove_source: bool = typer.Option(False, "--remove-source", help="also delete the checkout"),
    purge_data: bool = typer.Option(False, "--purge-data", help="also delete config, projects, and memory"),
    yes: bool = typer.Option(False, "--yes", "-y", help="skip confirmation"),
):
    """Uninstall cyberspace. Saved projects and configuration are kept by default."""
    import os
    import sys
    from pathlib import Path
    from rich.prompt import Confirm
    from .config import HOME
    from .uninstall import remove_installation

    standalone = bool(getattr(sys, "frozen", False))
    root = Path(os.environ.get("CYBERSPACE_ROOT", Path(__file__).resolve().parents[1]))
    launcher = (Path(sys.executable) if standalone else Path(os.environ.get(
        "CYBERSPACE_LAUNCHER_PATH", Path.home() / ".local" / "bin" / "cyberspace")))
    extras = []
    if remove_source:
        extras.append("source checkout")
    if purge_data:
        extras.append("saved projects/configuration")
    detail = ", ".join(extras) if extras else "standalone executable"
    if not yes and not Confirm.ask(f"Remove cyberspace ({detail})?", default=False):
        console.print("[dim]Uninstall cancelled.[/dim]")
        return
    for action in remove_installation(root, launcher, HOME,
                                      remove_source=remove_source, purge_data=purge_data,
                                      standalone=standalone):
        console.print(f"[green]✓[/green] {action}")
    if not purge_data:
        console.print(f"[dim]Saved projects and configuration kept at {HOME}[/dim]")
    console.print("[green]Cyberspace uninstalled.[/green]")


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
