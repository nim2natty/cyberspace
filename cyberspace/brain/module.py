"""Brain module - registers the flagship orchestrator into cyberspace.

The Brain is the backbone: it feeds swarm, airbender, shadowdragon, stickem,
and iceberg by planning multi-tool Kill Chain operations, acquiring any missing
software, executing sub-tasks concurrently, compiling comprehensive reports, and
learning from each outcome so the instance keeps getting sharper.
"""
from __future__ import annotations

from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.table import Table

from ..modules.base import Module, ModuleInfo, Tool, ToolRegistry

console = Console()


def _tool_run(intent: str = ""):
    """Agent-callable: run the full evolving Brain pipeline on an objective."""
    if not intent:
        return "intent required (the objective in plain language)"
    from .brain import run
    def on_event(stage, msg):
        console.print(f"  [dim]{stage:>8}[/dim]  {msg}")
    outcome = run(intent, on_event=on_event)
    return outcome.report[:4000]


def _tool_plan(intent: str = ""):
    """Agent-callable: show the Brain's multi-tool plan without executing."""
    from .brain import plan_only
    return plan_only(intent or "(no intent)")


def _tool_recall(query: str = ""):
    """Agent-callable: recall past operations from the playbook."""
    from .playbook import recall
    rows = recall(query or "", limit=5)
    if not rows:
        return "no past operations match."
    return "\n".join(f"- [{r.get('stage')}] success={r.get('success')} tools={r.get('tools')}: "
                     f"{r.get('outcome','')[:100]}" for r in rows)


def _tool_stats():
    """Agent-callable: report playbook statistics."""
    from .playbook import stats
    s = stats()
    return (f"playbook: {s['total']} operations ({s['successes']} ok, "
            f"{s['failures']} failed). tools seen: {', '.join(s['tools_used'][:15])}")


def _tool_acquire(tool: str = ""):
    """Agent-callable: find the install path for a missing tool."""
    if not tool:
        return "tool name required"
    from .acquire import resolve_tools
    resolved = resolve_tools([tool])
    info = resolved.get(tool, {})
    if info.get("installed"):
        return f"{tool} is already installed."
    cand = info.get("candidate")
    if not cand:
        return f"no install candidate found for {tool}."
    return (f"{tool}: source={cand.source}, command='{cand.install_command}'. "
            f"{cand.note}")


class BrainModule(Module):
    def describe(self) -> ModuleInfo:
        return ModuleInfo(
            name="brain", display_name="Brain", version="0.1.0",
            emoji="\U0001F9E0",
            description="The evolving orchestration backbone: plan multi-tool Kill Chain "
                        "operations, acquire software, run sub-agents concurrently, compile "
                        "comprehensive reports, and learn from each outcome.",
            requires_tools=[],
        )

    def register_tools(self, registry: ToolRegistry) -> None:
        registry.register(Tool(
            name="brain.run",
            description="Run the full evolving Brain pipeline on an objective: plan a "
                        "multi-tool Cyber Kill Chain operation, acquire any missing software, "
                        "execute sub-tasks concurrently across swarm/airbender/shadowdragon/"
                        "stickem/iceberg, compile a comprehensive report with artifact links, "
                        "and learn the outcome. Use for any multi-step security objective.",
            parameters={"type": "object",
                        "properties": {"intent": {"type": "string",
                                                    "description": "the objective in plain language"}},
                        "required": ["intent"]}, fn=_tool_run))
        registry.register(Tool(
            name="brain.plan",
            description="Show the Brain's multi-tool Kill Chain plan for an objective without executing it.",
            parameters={"type": "object",
                        "properties": {"intent": {"type": "string"}},
                        "required": ["intent"]}, fn=_tool_plan))
        registry.register(Tool(
            name="brain.recall",
            description="Recall past operations from the playbook (what worked/failed before).",
            parameters={"type": "object",
                        "properties": {"query": {"type": "string", "default": ""}},
                        "required": []}, fn=_tool_recall))
        registry.register(Tool(
            name="brain.stats",
            description="Report playbook statistics (operations, successes, tools seen).",
            parameters={"type": "object", "properties": {}}, fn=_tool_stats))
        registry.register(Tool(
            name="brain.acquire",
            description="Find the install path for a missing host tool (catalog + web search).",
            parameters={"type": "object",
                        "properties": {"tool": {"type": "string"}},
                        "required": ["tool"]}, fn=_tool_acquire))

    def build_cli(self) -> typer.Typer:
        app = typer.Typer(help="Brain: the evolving orchestration backbone.")

        @app.command("run")
        def cli_run(objective: str = typer.Argument("", help="the objective in plain language")):
            """Run the full evolving Brain pipeline on an objective."""
            if not objective:
                objective = Prompt.ask("What is your authorized objective?")
            from .brain import run
            console.print(Panel.fit(
                "[bold magenta]Brain[/bold magenta] - evolving orchestration backbone\n"
                "plan -> acquire -> execute (concurrent) -> report -> learn",
                border_style="magenta"))
            def on_event(stage, msg):
                console.print(f"  [dim]{stage:>8}[/dim]  {msg}")
            outcome = run(objective, on_event=on_event)
            console.print(Panel(outcome.report[:6000], title="Brain report",
                                border_style="green" if outcome.success else "yellow"))

        @app.command("plan")
        def cli_plan(objective: str = typer.Argument("", help="the objective to plan")):
            """Show the multi-tool Kill Chain plan without executing."""
            if not objective:
                objective = Prompt.ask("What is your objective?")
            from .brain import plan_only
            console.print(plan_only(objective))

        @app.command("recall")
        def cli_recall(query: str = typer.Argument("", help="search past operations")):
            """Search the playbook of past operations."""
            from .playbook import recall
            rows = recall(query, limit=10)
            if not rows:
                console.print("[dim]no past operations match.[/dim]"); return
            t = Table("stage", "success", "tools", "outcome")
            for r in rows:
                t.add_row(r.get("stage", ""), str(r.get("success", "")),
                          ", ".join(r.get("tools", [])), r.get("outcome", "")[:80])
            console.print(t)

        @app.command("stats")
        def cli_stats():
            """Show playbook statistics."""
            from .playbook import stats
            s = stats()
            console.print(Panel.fit(
                f"operations: {s['total']} ({s['successes']} ok, {s['failures']} failed)\n"
                f"tools seen: {', '.join(s['tools_used']) or '(none yet)'}",
                title="Brain playbook", border_style="magenta"))

        @app.command("acquire")
        def cli_acquire(tool: str = typer.Argument(..., help="tool binary name")):
            """Find the install path for a missing tool (catalog + web)."""
            from .acquire import resolve_tools
            resolved = resolve_tools([tool])
            info = resolved.get(tool, {})
            if info.get("installed"):
                console.print(f"[green]{tool} is already installed.[/green]"); return
            cand = info.get("candidate")
            if not cand:
                console.print(f"[red]no install candidate found for {tool}.[/red]"); return
            console.print(Panel.fit(
                f"tool: {cand.name}\nsource: {cand.source}\ncommand: {cand.install_command}\n"
                f"note: {cand.note}\nurl: {cand.url or '(none)'}",
                title="Install candidate", border_style="cyan"))

        return app


MODULE = BrainModule()
