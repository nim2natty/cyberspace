"""IceBerg module - OPSEC browser + system opsec platform.

Combines the veil-derived anti-detect browser (custom fingerprints, DoH, proxy,
WebRTC leak prevention, canvas/WebGL/audio noise) with system-level OPSEC
(mac rotation, hostname, tor/proxychains). One platform for staying hidden.
"""
from __future__ import annotations

from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from ...modules.base import Module, ModuleInfo, Tool, ToolRegistry
from .profiles import FingerprintProfile
from .personas import PERSONAS
from . import opsec

console = Console()


# --- agent tool functions --------------------------------------------------- #
def _tool_browser(profile: str = "", url: str = "", selftest: bool = False):
    if not profile:
        names = FingerprintProfile.list_names()
        return "No profile specified. Available: " + (", ".join(names) if names else "(none)")
    from .browser import launch
    try:
        p = FingerprintProfile.load(profile)
    except FileNotFoundError as e:
        return str(e)
    # Agent-driven launch is headless by default; returns a status string.
    launch(p, url=url or None, headless=True, selftest=selftest)
    return f"launched IceBerg browser with profile {profile}"


def _tool_opsec_check(**_):
    return opsec.selfcheck()


def _tool_new_profile(name: str = "auto", persona: str = "win-chrome"):
    p = FingerprintProfile.from_persona(name, persona)
    p.save()
    return f"created IceBerg profile '{name}' from persona '{persona}'"


class IceBergModule(Module):
    def describe(self) -> ModuleInfo:
        return ModuleInfo(
            name="iceberg", display_name="IceBerg", version="0.1.0",
            emoji="\U0001f9ca",
            description="OPSEC browser + system opsec (anti-detect, DoH, proxy, WebRTC, MAC).",
            requires_tools=["playwright", "macchanger", "tor", "proxychains"],
        )

    def register_tools(self, registry: ToolRegistry) -> None:
        registry.register(Tool(
            name="iceberg.browse",
            description="Launch the anti-detect IceBerg browser with a saved profile.",
            parameters={"type": "object",
                        "properties": {"profile": {"type": "string"},
                                       "url": {"type": "string", "default": ""},
                                       "selftest": {"type": "boolean", "default": False}},
                        "required": ["profile"]}, fn=_tool_browser))
        registry.register(Tool(
            name="iceberg.opsec_check",
            description="Read out the current system OPSEC posture (tools present, hostname).",
            parameters={"type": "object", "properties": {}}, fn=_tool_opsec_check))
        registry.register(Tool(
            name="iceberg.new_profile",
            description="Create a new IceBerg fingerprint profile from a persona.",
            parameters={"type": "object",
                        "properties": {"name": {"type": "string"},
                                       "persona": {"type": "string", "default": "win-chrome"}},
                        "required": ["name"]}, fn=_tool_new_profile))

    def build_cli(self) -> typer.Typer:
        app = typer.Typer(help="IceBerg: OPSEC browser + system opsec.")
        prof_app = typer.Typer(help="Manage fingerprint profiles.")
        app.add_typer(prof_app, name="profile")

        @app.command("browse")
        def browse(url: Optional[str] = typer.Argument(None),
                   profile: str = typer.Option(..., "-p"),
                   headless: bool = typer.Option(False),
                   selftest: bool = typer.Option(False, help="offline fingerprint check")):
            """Launch a spoofed, sealed browser session with live query visibility."""
            try:
                p = FingerprintProfile.load(profile)
            except FileNotFoundError as e:
                console.print(f"[red]{e}[/red]"); raise typer.Exit(1)
            from .browser import launch
            launch(p, url=url, headless=headless, selftest=selftest, console=console)

        @prof_app.command("new")
        def prof_new(name: str = typer.Argument(...),
                     persona: str = typer.Option("win-chrome", "--persona", "-p"),
                     proxy: Optional[str] = typer.Option(None),
                     doh: str = typer.Option("mullvad")):
            p = FingerprintProfile.from_persona(name, persona, proxy=proxy, doh_provider=doh)
            p.save()
            console.print(f"[green]created[/green] IceBerg profile [bold]{name}[/bold]")

        @prof_app.command("list")
        def prof_list():
            t = Table("profile", "persona platform", "tz", "proxy")
            for n in FingerprintProfile.list_names():
                p = FingerprintProfile.load(n)
                t.add_row(n, p.platform, p.timezone, p.proxy or "-")
            console.print(t or "[dim]none yet[/dim]")

        @prof_app.command("personas")
        def prof_personas():
            t = Table("persona", "platform", "screen", "tz")
            for k, v in PERSONAS.items():
                t.add_row(k, v["platform"],
                          f"{v['screen_width']}x{v['screen_height']}", v["timezone"])
            console.print(t)

        @app.command("rotate-mac")
        def rotate_mac(iface: str = typer.Option("eth0", "--iface")):
            console.print(opsec.rotate_mac(iface))

        @app.command("set-hostname")
        def set_host(name: str = typer.Argument("opsec-host")):
            console.print(opsec.set_hostname(name))

        @app.command("check")
        def check():
            console.print(opsec.selfcheck())

        return app


MODULE = IceBergModule()
