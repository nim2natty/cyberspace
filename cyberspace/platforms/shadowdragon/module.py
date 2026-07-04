"""ShadowDragon module - all non-networking Kali tools.

Layered over Kali Linux. Covers web apps, exploitation, password attacks,
recon/OSINT, post-exploitation/AD, sniffing & MITM, forensics, crypto/stego,
reverse engineering, and database assessment. Networking/scanning belongs to
AirBender. Curated wrappers handle common tools; kali_run drives the rest.
"""
from __future__ import annotations

import typer
from rich.console import Console
from rich.table import Table

from ...modules.base import Module, ModuleInfo, Tool, ToolRegistry
from ...host import is_available
from . import tools as T
from .catalog import KALI_CATALOG, all_tools

console = Console()


def _chain_tool(target="", pipeline="", steps=""):
    from .chain import run_chain, PIPELINES
    if steps and "->" in steps:
        sl = [s.strip() for s in steps.split("->")]
    elif pipeline and pipeline in PIPELINES:
        sl = PIPELINES[pipeline]["steps"]
    else:
        sl = ["whatweb", "searchsploit"]
    results = run_chain(sl, target)
    return "\n---\n".join(f"[{k}]\n{v}" for k, v in results.items())


def _msf_search_tool(query=""):
    from .metasploit import search
    return search(query)


def _msf_run_tool(module="", options="", lhost="", lport=4444):
    from .metasploit import run_exploit
    return run_exploit(module, options, lhost, lport)


class ShadowDragonModule(Module):
    def describe(self) -> ModuleInfo:
        return ModuleInfo(
            name="shadowdragon", display_name="ShadowDragon", version="0.1.0",
            emoji="\U0001f40d",
            description="All non-networking Kali tools (web, exploit, creds, recon, post-exploit).",
            requires_tools=all_tools()[:14],
        )

    def register_tools(self, registry: ToolRegistry) -> None:
        reg = registry.register
        reg(Tool(name="shadowdragon.sqlmap",
                 description="Test a URL for SQL injection with sqlmap (batch).",
                 parameters={"type": "object", "properties": {
                     "url": {"type": "string"}, "level": {"type": "integer", "default": 1},
                     "risk": {"type": "integer", "default": 1},
                     "extra": {"type": "string", "default": ""}}, "required": ["url"]}, fn=T.sqlmap))
        reg(Tool(name="shadowdragon.gobuster",
                 description="Directory/file brute force with gobuster.",
                 parameters={"type": "object", "properties": {
                     "url": {"type": "string"},
                     "wordlist": {"type": "string", "default": "/usr/share/wordlists/dirb/common.txt"}},
                     "required": ["url"]}, fn=T.gobuster))
        reg(Tool(name="shadowdragon.whatweb",
                 description="Identify web technologies with whatweb.",
                 parameters={"type": "object", "properties": {"url": {"type": "string"}},
                             "required": ["url"]}, fn=T.whatweb))
        reg(Tool(name="shadowdragon.nikto",
                 description="Web server vulnerability scan with nikto.",
                 parameters={"type": "object", "properties": {"url": {"type": "string"}},
                             "required": ["url"]}, fn=T.nikto))
        reg(Tool(name="shadowdragon.searchsploit",
                 description="Search exploitdb for public exploits.",
                 parameters={"type": "object", "properties": {"query": {"type": "string"}},
                             "required": ["query"]}, fn=T.searchsploit))
        reg(Tool(name="shadowdragon.john",
                 description="Offline password/hash cracking with John the Ripper.",
                 parameters={"type": "object", "properties": {
                     "hashfile": {"type": "string"},
                     "wordlist": {"type": "string", "default": "/usr/share/wordlists/rockyou.txt"}},
                     "required": ["hashfile"]}, fn=T.john))
        reg(Tool(name="shadowdragon.hashcat",
                 description="GPU/accelerated hash cracking with hashcat.",
                 parameters={"type": "object", "properties": {
                     "hash": {"type": "string"}, "mode": {"type": "integer", "default": 0},
                     "wordlist": {"type": "string", "default": "/usr/share/wordlists/rockyou.txt"}},
                     "required": ["hash"]}, fn=T.hashcat))
        reg(Tool(name="shadowdragon.hydra",
                 description="Online brute force of a login service with hydra.",
                 parameters={"type": "object", "properties": {
                     "target": {"type": "string"}, "service": {"type": "string", "default": "ssh"},
                     "users": {"type": "string"}, "passwords": {"type": "string"}},
                     "required": ["target"]}, fn=T.hydra))
        reg(Tool(name="shadowdragon.theharvester",
                 description="OSINT recon (emails, hosts, names) for a domain.",
                 parameters={"type": "object", "properties": {"domain": {"type": "string"}},
                             "required": ["domain"]}, fn=T.theharvester))
        reg(Tool(name="shadowdragon.secretsdump",
                 description="Dump NTLM hashes / secrets via impacket-secretsdump.",
                 parameters={"type": "object", "properties": {"target": {"type": "string"}},
                             "required": ["target"]}, fn=T.secretsdump))
        reg(Tool(name="shadowdragon.kali_run",
                 description=("Run ANY non-networking Kali tool by name + args. Covers "
                              "everything not in AirBender. Use kali_catalog to see options."),
                 parameters={"type": "object", "properties": {
                     "name": {"type": "string", "description": "Kali binary name"},
                     "args": {"type": "string", "default": "", "description": "space-separated arguments"},
                     "timeout": {"type": "integer", "default": 300}},
                     "required": ["name"]}, fn=T.kali_run))
        reg(Tool(name="shadowdragon.kali_catalog",
                 description="List all Kali tools ShadowDragon can run, by category.",
                 parameters={"type": "object", "properties": {}}, fn=T.kali_catalog))
        reg(Tool(name="shadowdragon.kali_installed",
                 description="Show which Kali tools are installed on this host.",
                 parameters={"type": "object", "properties": {}}, fn=T.kali_installed))
        reg(Tool(name="shadowdragon.chain",
                 description="Run an interlinked attack pipeline. pipelines: web-recon, wp-assault, "
                 "sqli-exploit, subdomain-hunt, full-assault. Or custom steps separated by '->'.",
                 parameters={"type": "object",
                             "properties": {"target": {"type": "string"},
                                            "pipeline": {"type": "string", "default": ""},
                                            "steps": {"type": "string", "default": ""}},
                             "required": ["target"]},
                 fn=lambda target="", pipeline="", steps="", **_: _chain_tool(target, pipeline, steps)))
        reg(Tool(name="shadowdragon.msf_search",
                 description="Search metasploit modules by keyword.",
                 parameters={"type": "object", "properties": {"query": {"type": "string"}},
                             "required": ["query"]},
                 fn=lambda query="", **_: _msf_search_tool(query)))
        reg(Tool(name="shadowdragon.msf_run",
                 description="Run a metasploit exploit module (e.g. exploit/windows/smb/ms17_010_eternalblue).",
                 parameters={"type": "object",
                             "properties": {"module": {"type": "string"},
                                            "options": {"type": "string", "default": ""},
                                            "lhost": {"type": "string", "default": ""},
                                            "lport": {"type": "integer", "default": 4444}},
                             "required": ["module"]},
                 fn=lambda module="", options="", lhost="", lport=4444, **_: _msf_run_tool(module, options, lhost, lport)))

    def build_cli(self) -> typer.Typer:
        app = typer.Typer(help="ShadowDragon: all non-networking Kali tools.")

        @app.command("sqlmap")
        def _sqlmap(url: str = typer.Argument(...), level: int = typer.Option(1), risk: int = typer.Option(1)):
            console.print(T.sqlmap(url=url, level=level, risk=risk))

        @app.command("gobuster")
        def _gobuster(url: str = typer.Argument(...), wordlist: str = typer.Option("/usr/share/wordlists/dirb/common.txt")):
            console.print(T.gobuster(url=url, wordlist=wordlist))

        @app.command("whatweb")
        def _whatweb(url: str = typer.Argument(...)):
            console.print(T.whatweb(url=url))

        @app.command("nikto")
        def _nikto(url: str = typer.Argument(...)):
            console.print(T.nikto(url=url))

        @app.command("searchsploit")
        def _searchsploit(query: str = typer.Argument(...)):
            console.print(T.searchsploit(query=query))

        @app.command("john")
        def _john(hashfile: str = typer.Argument(...), wordlist: str = typer.Option("/usr/share/wordlists/rockyou.txt")):
            console.print(T.john(hashfile=hashfile, wordlist=wordlist))

        @app.command("hashcat")
        def _hashcat(hash: str = typer.Argument(...), mode: int = typer.Option(0), wordlist: str = typer.Option("/usr/share/wordlists/rockyou.txt")):
            console.print(T.hashcat(hash=hash, mode=mode, wordlist=wordlist))

        @app.command("hydra")
        def _hydra(target: str = typer.Argument(...), service: str = typer.Option("ssh")):
            console.print(T.hydra(target=target, service=service))

        @app.command("theharvester")
        def _theharvester(domain: str = typer.Argument(...)):
            console.print(T.theharvester(domain=domain))

        @app.command("run")
        def _run(name: str = typer.Argument(..., help="Kali tool name"), args: str = typer.Argument("", help="quoted args"), timeout: int = typer.Option(300)):
            """Run any non-networking Kali tool by name."""
            console.print(T.kali_run(name=name, args=args, timeout=timeout))

        @app.command("catalog")
        def _catalog():
            """List all tools ShadowDragon can run, by category."""
            t = Table("category", "tools")
            for cat, tools in KALI_CATALOG.items():
                t.add_row(cat, ", ".join(tools))
            console.print(t)

        # --- super-tool: chain + metasploit -------------------------------- #
        @app.command("chain")
        def _chain(target: str = typer.Argument(...),
                    steps: str = typer.Option("", "--steps",
                    help="custom steps: 'whatweb->searchsploit->metasploit'")):
            """Run interlinked attack tools as a pipeline."""
            from .chain import CHAIN_STEPS, run_chain
            sl = [s.strip() for s in steps.split("->")] if steps else ["whatweb", "searchsploit"]
            for name, result in run_chain(sl, target,
                    lambda s,m: console.print(f"[dim]{s:>14}[/dim] {m}")).items():
                console.print(f"\n[bold red]{'='*40} {name} {'='*40}[/bold red]")
                console.print(result)

        @app.command("pipelines")
        def _pipelines():
            """Show available attack pipelines."""
            from .chain import PIPELINES
            t = Table("pipeline", "steps", "description")
            for name, p in PIPELINES.items():
                t.add_row(name, " -> ".join(p["steps"]), p["desc"])
            console.print(t)
            console.print("\n[dim]Custom: cyberspace shadowdragon chain <target> --steps 'whatweb->searchsploit->metasploit'[/dim]")

        @app.command("web-recon")
        def _webrecon(target: str = typer.Argument(...)):
            """Pipeline: whatweb -> nuclei -> searchsploit."""
            from .chain import run_chain, PIPELINES
            for name, result in run_chain(PIPELINES["web-recon"]["steps"], target,
                    lambda s,m: console.print(f"[dim]{s:>14}[/dim] {m}")).items():
                console.print(f"\n[bold red]{'='*40} {name} {'='*40}[/bold red]")
                console.print(result)

        @app.command("full-assault")
        def _assault(target: str = typer.Argument(...)):
            """Pipeline: whatweb -> gobuster -> nikto -> searchsploit -> metasploit."""
            from .chain import run_chain, PIPELINES
            for name, result in run_chain(PIPELINES["full-assault"]["steps"], target,
                    lambda s,m: console.print(f"[dim]{s:>14}[/dim] {m}")).items():
                console.print(f"\n[bold red]{'='*40} {name} {'='*40}[/bold red]")
                console.print(result)

        # --- metasploit --------------------------------------------------- #
        msf_app = typer.Typer(help="Metasploit: search, run exploits, handlers, payloads.")
        app.add_typer(msf_app, name="msf")

        @msf_app.command("search")
        def _msf_search(query: str = typer.Argument(...)):
            """Search metasploit modules."""
            from .metasploit import search
            console.print(search(query))

        @msf_app.command("run")
        def _msf_run(module: str = typer.Argument(..., help="exploit/windows/smb/ms17_010_eternalblue"),
                     options: str = typer.Option("", "--options", help="RHOSTS=10.10.10.5"),
                     lhost: str = typer.Option(""), lport: int = typer.Option(4444)):
            """Run a metasploit exploit module."""
            from .metasploit import run_exploit
            console.print(run_exploit(module, options, lhost, lport))

        @msf_app.command("handler")
        def _msf_handler(payload: str = typer.Option("windows/meterpreter/reverse_tcp"),
                         lhost: str = typer.Option("0.0.0.0"), lport: int = typer.Option(4444)):
            """Start a multi/handler to catch a reverse shell."""
            from .metasploit import handler
            console.print(handler(payload, lhost, lport))

        @msf_app.command("payload")
        def _msf_payload(payload: str = typer.Option("windows/meterpreter/reverse_tcp"),
                         lhost: str = typer.Option(""), lport: int = typer.Option(4444),
                         fmt: str = typer.Option("raw"), outfile: str = typer.Option("")):
            """Generate a payload with msfvenom."""
            from .metasploit import payload_generate
            console.print(payload_generate(payload, lhost, lport, fmt, outfile))

        return app


MODULE = ShadowDragonModule()
