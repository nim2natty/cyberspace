"""Register Cyberdeck orchestration, prompt records, and CLI commands.

Cyberdeck plans multi-tool Kill Chain operations, resolves missing software,
executes independent tasks concurrently, evaluates outputs, compiles reports,
stores user prompts, and records verified operation outcomes.
"""
from __future__ import annotations

from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.table import Table
from rich.markup import escape

from ..modules.base import Module, ModuleInfo, Tool, ToolRegistry

console = Console()


def _tool_run(intent: str = ""):
    """Agent-callable: plan, execute, evaluate, and report an objective."""
    if not intent:
        return "intent required (the objective in plain language)"
    from .cyberdeck import run
    def on_event(stage, msg):
        console.print(f"  [dim]{stage:>8}[/dim]  {msg}")
    outcome = run(intent, on_event=on_event)
    return outcome.report[:4000]


def _tool_plan(intent: str = ""):
    """Agent-callable: show the Cyberdeck's multi-tool plan without executing."""
    from .cyberdeck import plan_only
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


def _tool_prompts(query: str = "", label: str = "", limit: int = 20):
    """Agent-callable: list ordered user prompt records from Cyberdeck."""
    from .prompts import list_prompts
    from ..projects import get_active
    rows = list_prompts(query=query, label=label, limit=limit,
                        project=get_active() or "")
    if not rows:
        return "no Cyberdeck prompts match"
    return "\n".join(
        f"#{row['sequence']} [{row['label']}] {row.get('source', '')}: "
        f"{row.get('prompt', '')[:180]}" for row in rows)


class CyberdeckModule(Module):
    def describe(self) -> ModuleInfo:
        return ModuleInfo(
            name="cyberdeck", display_name="Cyberdeck", version="0.1.0",
            emoji="\U0001F9E0",
            description="Plan multi-tool Kill Chain operations, resolve host dependencies, "
                        "execute independent tasks concurrently, evaluate output evidence, "
                        "compile reports, and store prompts and verified outcomes.",
            requires_tools=[],
        )

    def register_tools(self, registry: ToolRegistry) -> None:
        registry.register(Tool(
            name="cyberdeck.run",
            description="Run the Cyberdeck pipeline on a security objective: plan a "
                        "multi-tool Cyber Kill Chain operation, acquire any missing software, "
                        "execute sub-tasks concurrently across swarm/airbender/shadowdragon/"
                        "stickem/iceberg, compile an evidence report with artifact links, "
                        "and learn the outcome. Use for any multi-step security objective.",
            parameters={"type": "object",
                        "properties": {"intent": {"type": "string",
                                                    "description": "the objective in plain language"}},
                        "required": ["intent"]}, fn=_tool_run))
        registry.register(Tool(
            name="cyberdeck.plan",
            description="Show the Cyberdeck's multi-tool Kill Chain plan for an objective without executing it.",
            parameters={"type": "object",
                        "properties": {"intent": {"type": "string"}},
                        "required": ["intent"]}, fn=_tool_plan))
        registry.register(Tool(
            name="cyberdeck.recall",
            description="Recall past operations from the playbook (what worked/failed before).",
            parameters={"type": "object",
                        "properties": {"query": {"type": "string", "default": ""}},
                        "required": []}, fn=_tool_recall))
        registry.register(Tool(
            name="cyberdeck.stats",
            description="Report playbook statistics (operations, successes, tools seen).",
            parameters={"type": "object", "properties": {}}, fn=_tool_stats))
        registry.register(Tool(
            name="cyberdeck.acquire",
            description="Find the install path for a missing host tool (catalog + web search).",
            parameters={"type": "object",
                        "properties": {"tool": {"type": "string"}},
                        "required": ["tool"]}, fn=_tool_acquire))
        registry.register(Tool(
            name="cyberdeck.prompts",
            description="List or search the ordered Cyberdeck records of user prompts.",
            parameters={"type": "object",
                        "properties": {"query": {"type": "string", "default": ""},
                                       "label": {"type": "string", "default": ""},
                                       "limit": {"type": "integer", "default": 20}}},
            fn=_tool_prompts))

    def build_cli(self) -> typer.Typer:
        app = typer.Typer(help="Cyberdeck: prompt records and staged security-tool orchestration.")

        @app.command("run")
        def cli_run(objective: str = typer.Argument("", help="the objective in plain language")):
            """Plan, execute, evaluate, and report a security objective."""
            if not objective:
                objective = Prompt.ask("What is your authorized objective?")
            from .prompts import record_prompt, complete_prompt
            prompt_record = record_prompt(objective, source="cyberdeck-run")
            from .cyberdeck import run
            console.print(Panel.fit(
                "[bold magenta]Cyberdeck[/bold magenta]\n"
                "plan -> resolve tools -> execute -> evaluate -> report -> record outcome",
                border_style="magenta"))
            def on_event(stage, msg):
                console.print(f"  [dim]{stage:>8}[/dim]  {msg}")
            try:
                outcome = run(objective, on_event=on_event)
            except Exception as exc:
                complete_prompt(prompt_record["sequence"], str(exc), status="failed")
                raise
            complete_prompt(prompt_record["sequence"], outcome.report,
                            status="completed" if outcome.success else "completed-with-errors")
            console.print(Panel(outcome.report[:6000], title="Cyberdeck report",
                                border_style="green" if outcome.success else "yellow"))

        @app.command("plan")
        def cli_plan(objective: str = typer.Argument("", help="the objective to plan")):
            """Show the multi-tool Kill Chain plan without executing."""
            if not objective:
                objective = Prompt.ask("What is your objective?")
            from .prompts import record_prompt, complete_prompt
            prompt_record = record_prompt(objective, source="cyberdeck-plan")
            from .cyberdeck import plan_only
            try:
                planned = plan_only(objective)
            except Exception as exc:
                complete_prompt(prompt_record["sequence"], str(exc), status="failed")
                raise
            complete_prompt(prompt_record["sequence"], planned)
            console.print(planned)

        @app.command("prompts")
        def cli_prompts(
            query: str = typer.Option("", "--query", "-q", help="filter label, prompt, or response text"),
            label: str = typer.Option("", "--label", "-l", help="filter by exact label"),
            limit: int = typer.Option(50, "--limit", min=1, max=1000),
        ):
            """List saved user prompts in their original order."""
            from .prompts import list_prompts
            rows = list_prompts(query=query, label=label, limit=limit)
            if not rows:
                console.print("[dim]no Cyberdeck prompts match[/dim]")
                return
            table = Table("#", "timestamp", "label", "source", "status", "prompt")
            for row in rows:
                table.add_row(str(row.get("sequence", "")), row.get("ts", "")[:19],
                              row.get("label", ""), row.get("source", ""),
                              row.get("status", ""), escape(row.get("prompt", "")[:100]))
            console.print(table)

        @app.command("prompt")
        def cli_prompt(sequence: int = typer.Argument(..., help="prompt sequence number")):
            """Show one saved prompt and its response."""
            from .prompts import get_prompt
            row = get_prompt(sequence)
            if not row:
                console.print(f"[red]no Cyberdeck prompt #{sequence}[/red]")
                raise typer.Exit(1)
            console.print(Panel(
                f"label: {row.get('label')} ({row.get('label_source')})\n"
                f"source: {row.get('source')}  project: {row.get('project') or '-'}\n"
                f"status: {row.get('status')}  timestamp: {row.get('ts')}\n\n"
                f"PROMPT\n{escape(row.get('prompt', ''))}\n\nRESPONSE\n"
                f"{escape(row.get('response', '') or '(none)')}",
                title=f"Cyberdeck prompt #{sequence}"))

        @app.command("label")
        def cli_label(sequence: int = typer.Argument(...),
                      label: str = typer.Argument(..., help="new label")):
            """Set the label for one saved prompt."""
            from .prompts import set_label
            if not set_label(sequence, label):
                console.print(f"[red]no Cyberdeck prompt #{sequence}[/red]")
                raise typer.Exit(1)
            console.print(f"[green]labeled prompt #{sequence}:[/green] {label}")

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
                title="Cyberdeck playbook", border_style="magenta"))

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


MODULE = CyberdeckModule()
