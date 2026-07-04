"""AirBender module - networking toolkit platform.

Wraps real networking tools (nmap, masscan, ...) behind one consistent CLI and
agent-tool interface. Each tool is detected at runtime and gives a friendly
'install me' hint if missing. The agent can call any of these in conversation.
"""
from __future__ import annotations

import ipaddress
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from ...modules.base import Module, ModuleInfo, Tool, ToolRegistry
from ...host import is_available, missing_hint, run

console = Console()


def _validate_target(target: str) -> Optional[str]:
    """Accept CIDR/IP/hostname; reject shell metacharacters. None if ok."""
    target = target.strip()
    bad = (" ", ";", "|", "&", "`", "$", "(", ")")
    if not target or any(c in target for c in bad):
        return "invalid target"
    return None


# --- agent tool functions --------------------------------------------------- #
def _tool_nmap(target: str = "127.0.0.1", args: str = "-sV -T4"):
    if not is_available("nmap"):
        return missing_hint("nmap")
    if _validate_target(target):
        return f"invalid target: {target}"
    safe_args = [a for a in args.split() if a and not any(c in a for c in ";|&`$()")]
    return run("nmap", [*safe_args, target], timeout=300).text()


def _tool_masscan(target: str = "127.0.0.1", ports: str = "1-1000", rate: int = 1000):
    if not is_available("masscan"):
        return missing_hint("masscan")
    if _validate_target(target):
        return f"invalid target: {target}"
    return run("masscan", ["-p" + ports, "--rate", str(rate), target], timeout=300).text()


def _tool_ping_sweep(target: str = "192.168.1.0/24"):
    if not is_available("nmap"):
        return missing_hint("nmap")
    if _validate_target(target):
        return f"invalid target: {target}"
    return run("nmap", ["-sn", target], timeout=120).text()


class AirBenderModule(Module):
    def describe(self) -> ModuleInfo:
        return ModuleInfo(
            name="airbender", display_name="AirBender", version="0.1.0",
            emoji="\U0001f4f6",
            description="Networking toolkit: nmap, masscan, host discovery, port scan.",
            requires_tools=["nmap", "masscan"],
        )

    def register_tools(self, registry: ToolRegistry) -> None:
        registry.register(Tool(
            name="airbender.nmap",
            description="Run nmap against a target (CIDR/IP/host you are authorized to test).",
            parameters={"type": "object",
                        "properties": {"target": {"type": "string"},
                                       "args": {"type": "string", "default": "-sV -T4"}},
                        "required": ["target"]}, fn=_tool_nmap))
        registry.register(Tool(
            name="airbender.masscan",
            description="Fast port scan with masscan (authorized target only).",
            parameters={"type": "object",
                        "properties": {"target": {"type": "string"},
                                       "ports": {"type": "string", "default": "1-1000"},
                                       "rate": {"type": "integer", "default": 1000}},
                        "required": ["target"]}, fn=_tool_masscan))
        registry.register(Tool(
            name="airbender.ping_sweep",
            description="Discover live hosts on a subnet via nmap -sn.",
            parameters={"type": "object",
                        "properties": {"target": {"type": "string", "default": "192.168.1.0/24"}}},
            fn=_tool_ping_sweep))

    def build_cli(self) -> typer.Typer:
        app = typer.Typer(help="AirBender: networking toolkit (nmap, masscan...).")

        @app.command("nmap")
        def nmap_cmd(target: str = typer.Argument(...),
                     args: str = typer.Option("-sV -T4", "--args")):
            """Run nmap against a target."""
            console.print(_tool_nmap(target=target, args=args))

        @app.command("masscan")
        def masscan_cmd(target: str = typer.Argument(...),
                        ports: str = typer.Option("1-1000"), rate: int = typer.Option(1000)):
            """Run masscan against a target."""
            console.print(_tool_masscan(target=target, ports=ports, rate=rate))

        @app.command("ping-sweep")
        def ping_cmd(target: str = typer.Argument("192.168.1.0/24")):
            """Discover live hosts."""
            console.print(_tool_ping_sweep(target=target))

        @app.command("status")
        def status():
            """Show which networking tools are installed."""
            t = Table("tool", "installed")
            for name in self.describe().requires_tools:
                t.add_row(name, "[green]yes[/green]" if is_available(name) else "[red]no[/red]")
            console.print(t)

        return app


MODULE = AirBenderModule()
