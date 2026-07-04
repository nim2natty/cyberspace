"""AirBender super-tool - ALL networking tools merged + interlinked.

Merges nmap, masscan, aircrack-ng suite, netdiscover, netcat, traceroute, whois,
dig, tcpdump under ONE CLI. The `chain` command runs interlinked pipelines so
tools feed into each other. Every action records to memory.
"""
from __future__ import annotations

import typer
from rich.console import Console
from rich.table import Table

from ...modules.base import Module, ModuleInfo, Tool, ToolRegistry
from . import chain as C

console = Console()


def _tool_chain(pipeline="", steps="", target="", **_):
    if steps and "->" in steps:
        step_list = [s.strip() for s in steps.split("->")]
    elif pipeline and pipeline in C.PIPELINES:
        step_list = C.PIPELINES[pipeline]["steps"]
    else:
        step_list = ["ping-sweep", "nmap-top"]
    results = C.run_chain(step_list, target)
    return "\n---\n".join(f"[{k}]\n{v}" for k, v in results.items())


def _run_pipeline(name: str, target: str, console):
    p = C.PIPELINES.get(name)
    if not p:
        return
    console.print(f"[bold cyan]pipeline: {name}[/bold cyan] ({p['desc']})")
    for step_name, result in C.run_chain(p["steps"], target,
            lambda s, m: console.print(f"[dim]{s:>12}[/dim] {m}")).items():
        console.print(f"\n[bold cyan]{'='*40} {step_name} {'='*40}[/bold cyan]")
        console.print(result)


class AirBenderModule(Module):
    def describe(self) -> ModuleInfo:
        return ModuleInfo(
            name="airbender", display_name="AirBender", version="0.2.0",
            emoji="\U0001f4f6",
            description="Super-tool: ALL networking (nmap, masscan, aircrack-ng, nc, dig...) interlinked.",
            requires_tools=C.NETWORKING_TOOLS,
        )

    def register_tools(self, registry: ToolRegistry) -> None:
        reg = registry.register
        reg(Tool(name="airbender.nmap", description="Run nmap against an authorized target.",
                 parameters={"type":"object","properties":{"target":{"type":"string"},
                  "args":{"type":"string","default":"-sV -T4"}},"required":["target"]}, fn=C._tool_nmap))
        reg(Tool(name="airbender.masscan", description="Fast port scan with masscan.",
                 parameters={"type":"object","properties":{"target":{"type":"string"},
                  "ports":{"type":"string","default":"1-1000"},"rate":{"type":"integer","default":1000}},
                  "required":["target"]}, fn=C._tool_masscan))
        reg(Tool(name="airbender.ping_sweep", description="Discover live hosts on a subnet.",
                 parameters={"type":"object","properties":{"target":{"type":"string",
                  "default":"192.168.1.0/24"}}}, fn=C._tool_ping_sweep))
        reg(Tool(name="airbender.whois", description="WHOIS lookup for a domain.",
                 parameters={"type":"object","properties":{"domain":{"type":"string"}},
                  "required":["domain"]}, fn=C._tool_whois))
        reg(Tool(name="airbender.dig", description="DNS query with dig.",
                 parameters={"type":"object","properties":{"domain":{"type":"string"},
                  "rtype":{"type":"string","default":"A"}},"required":["domain"]}, fn=C._tool_dig))
        reg(Tool(name="airbender.chain",
                 description="Run an interlinked networking pipeline. pipelines: "+
                 ", ".join(C.PIPELINES)+". steps: "+", ".join(C.CHAIN_STEPS),
                 parameters={"type":"object","properties":{"pipeline":{"type":"string"},
                  "steps":{"type":"string","description":"custom steps separated by '->'"},
                  "target":{"type":"string"}},"required":["target"]}, fn=_tool_chain))

    def build_cli(self) -> typer.Typer:
        from ...host import is_available
        app = typer.Typer(help="AirBender super-tool: ALL networking tools interlinked.")

        @app.command("nmap")
        def _nmap(target: str = typer.Argument(...), args: str = typer.Option("-sV -T4","--args")):
            console.print(C._tool_nmap(target=target, args=args))
        @app.command("masscan")
        def _masscan(target: str = typer.Argument(...), ports: str = typer.Option("1-1000"),
                     rate: int = typer.Option(1000)):
            console.print(C._tool_masscan(target=target, ports=ports, rate=rate))
        @app.command("ping-sweep")
        def _ping(target: str = typer.Argument("192.168.1.0/24")):
            console.print(C._tool_ping_sweep(target=target))
        @app.command("whois")
        def _whois(domain: str = typer.Argument(...)):
            console.print(C._tool_whois(domain=domain))
        @app.command("dig")
        def _dig(domain: str = typer.Argument(...), rtype: str = typer.Option("A")):
            console.print(C._tool_dig(domain=domain, rtype=rtype))
        @app.command("traceroute")
        def _trace(target: str = typer.Argument("8.8.8.8")):
            console.print(C._tool_traceroute(target=target))
        @app.command("netdiscover")
        def _nd(target: str = typer.Argument("192.168.1.0/24")):
            console.print(C._tool_netdiscover(target=target))
        @app.command("arp-scan")
        def _arp():
            console.print(C._tool_arp_scan())
        @app.command("netcat")
        def _nc(target: str = typer.Argument(...), port: int = typer.Argument(80)):
            console.print(C._tool_netcat(target=target, port=port))
        @app.command("tcpdump")
        def _tcpdump(interface: str = typer.Option("eth0"), count: int = typer.Option(10)):
            console.print(C._tool_tcpdump(interface=interface, count=count))
        @app.command("airmon")
        def _airmon(iface: str = typer.Option("wlan0"), action: str = typer.Option("start")):
            console.print(C._tool_airmon(iface=iface, action=action))
        @app.command("airodump")
        def _airodump(iface: str = typer.Option("wlan0mon")):
            console.print(C._tool_airodump(iface=iface))
        @app.command("chain")
        def _chain(target: str = typer.Argument(...),
                    steps: str = typer.Option("", "--steps",
                    help="custom steps: 'ping-sweep->nmap-top->service-detect'")):
            """Run interlinked tools as a pipeline."""
            sl = [s.strip() for s in steps.split("->")] if steps else ["ping-sweep","nmap-top"]
            for name, result in C.run_chain(sl, target,
                    lambda s,m: console.print(f"[dim]{s:>12}[/dim] {m}")).items():
                console.print(f"\n[bold cyan]{'='*40} {name} {'='*40}[/bold cyan]")
                console.print(result)
        @app.command("recon")
        def _recon(target: str = typer.Argument(...)):
            """Full recon: discover hosts -> scan ports -> detect services."""
            _run_pipeline("recon", target, console)
        @app.command("fast-scan")
        def _fast(target: str = typer.Argument(...)):
            """Quick: discover hosts -> masscan all ports."""
            _run_pipeline("fast-scan", target, console)
        @app.command("web-hunt")
        def _web(target: str = typer.Argument(...)):
            """Find web apps: discover hosts -> detect web ports."""
            _run_pipeline("web-hunt", target, console)
        @app.command("pipelines")
        def _pipelines():
            """Show available interlinked pipelines."""
            t = Table("pipeline", "steps", "description")
            for name, p in C.PIPELINES.items():
                t.add_row(name, " -> ".join(p["steps"]), p["desc"])
            console.print(t)
            console.print("\n[dim]Custom: cyberspace airbender chain <target> --steps 'ping-sweep->nmap-top'[/dim]")
        @app.command("status")
        def _status():
            """Show which networking tools are installed."""
            t = Table("tool", "installed")
            for n in C.NETWORKING_TOOLS:
                t.add_row(n, "[green]yes[/green]" if is_available(n) else "[red]no[/red]")
            console.print(t)
        return app


MODULE = AirBenderModule()

