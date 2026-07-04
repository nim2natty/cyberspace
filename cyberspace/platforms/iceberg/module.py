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


def _tool_secure_find(query: str = "", mode: str = "bright", preset: str = "general"):
    """Agent-callable: run the IceBerg :: secure AI find pipeline (bright/dark)."""
    if not query:
        return "query required (e.g. iceberg.secure_find query='ransomware group X', mode='dark')"
    from .secure.pipeline import run_find
    from .secure.security import SecurityConfig
    sec = SecurityConfig.load()
    if mode in ("bright", "dark"):
        sec.mode = mode
    inv = run_find(query, sec=sec, preset=preset)
    head = (f"[mode={inv.mode} results={len(inv.results)} filtered={len(inv.filtered)} "
            f"scraped={len(inv.scraped)}]\n")
    return head + (inv.summary or "(no summary)")


def _tool_secure_status(**_):
    """Agent-callable: report IceBerg :: secure mode + Tor reachability."""
    from .secure.tor import tor_available
    from .secure.security import SecurityConfig, dark_settings
    sec = SecurityConfig.load()
    up = tor_available(sec.tor_socks_host, sec.tor_socks_port)
    lines = [f"secure mode: {sec.mode}", f"Tor SOCKS ({sec.socks_url()}): {'up' if up else 'down'}"]
    if sec.mode == "dark":
        lines += dark_settings(sec)
    return "\n".join(lines)


class IceBergModule(Module):
    def describe(self) -> ModuleInfo:
        return ModuleInfo(
            name="iceberg", display_name="IceBerg", version="0.1.0",
            emoji="\U0001f9ca",
            description="OPSEC browser + system opsec + 'e' AI find (bright/dark, Tor).",
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
        registry.register(Tool(
            name="iceberg.secure_find",
            description="AI-powered OSINT find: refine a query, search clearnet (bright) or "
                        "Tor onion engines (dark), filter, scrape, and summarize. "
                        "mode='dark' requires Tor. Use iceberg.secure_status first.",
            parameters={"type": "object",
                        "properties": {"query": {"type": "string"},
                                       "mode": {"type": "string", "enum": ["bright", "dark"],
                                                "default": "bright"},
                                       "preset": {"type": "string",
                                                  "enum": ["general", "threat_intel",
                                                           "personal_identity",
                                                           "corporate_espionage"],
                                                  "default": "general"}},
                        "required": ["query"]}, fn=_tool_secure_find))
        registry.register(Tool(
            name="iceberg.secure_status",
            description="Report IceBerg :: secure mode and whether the Tor SOCKS proxy is reachable.",
            parameters={"type": "object", "properties": {}}, fn=_tool_secure_status))

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

        # Switch the active cyberbot LLM model/provider (used by all platforms).
        model_app = typer.Typer(help="Switch the cyberbot LLM model / provider.")
        app.add_typer(model_app, name="model")

        @model_app.command("list")
        def model_list():
            """Show the current model + available models for the provider."""
            from ...agent.config import is_configured, load_config
            from ...config import SUGGESTED_MODELS, DEFAULT_OLLAMA_URL
            if not is_configured():
                console.print("[red]Agent not configured.[/red] Run: cyberspace setup")
                raise typer.Exit(1)
            cfg = load_config()
            console.print(f"[bold]current:[/bold] {cfg.provider}/{cfg.model}  "
                          f"[dim]@ {cfg.base_url}[/dim]\n")
            t = Table("model", "source")
            if cfg.provider == "ollama":
                import httpx
                try:
                    names = [m["name"] for m in
                             httpx.get(f"{cfg.base_url}/api/tags", timeout=3).json().get("models", [])]
                except Exception:
                    names = []
                for n in names:
                    t.add_row(n, "installed (ollama)")
            for n in SUGGESTED_MODELS.get(cfg.provider, []):
                t.add_row(n, "suggested")
            console.print(t or "[dim]no models known[/dim]")

        @model_app.command("switch")
        def model_switch(model: str = typer.Argument(..., help="model name to use")):
            """Switch the active model (keeps provider + base_url + api_key)."""
            from ...agent.config import is_configured, load_config, save_config
            if not is_configured():
                console.print("[red]Agent not configured.[/red] Run: cyberspace setup")
                raise typer.Exit(1)
            cfg = load_config()
            old = cfg.model
            cfg.model = model
            save_config(cfg)
            console.print(f"[green]switched model:[/green] {old} -> [bold]{model}[/bold]\n"
                          f"[dim]provider {cfg.provider} @ {cfg.base_url} unchanged.[/dim]")

        @model_app.command("provider")
        def model_provider(provider: str = typer.Argument(...,
                            help="ollama|openai|anthropic|custom"),
                           model: str = typer.Option("", "--model"),
                           base_url: str = typer.Option("", "--base-url"),
                           api_key: str = typer.Option("", "--api-key")):
            """Switch provider (and optionally model/url/key) in one step."""
            from ...agent.config import is_configured, load_config, save_config
            from ...agent.llm import LLMConfig
            from ...config import DEFAULT_OLLAMA_URL, SUGGESTED_MODELS
            existing = load_config() if is_configured() else None
            provider = provider.lower()
            if provider not in ("ollama", "openai", "anthropic", "custom"):
                console.print(f"[red]unknown provider '{provider}'[/red]"); raise typer.Exit(1)
            cfg = existing or LLMConfig()
            cfg.provider = provider
            cfg.base_url = base_url or (DEFAULT_OLLAMA_URL if provider == "ollama"
                                        else (existing.base_url if existing else ""))
            if api_key:
                cfg.api_key = api_key
            if model:
                cfg.model = model
            elif not cfg.model:
                cfg.model = SUGGESTED_MODELS.get(provider, ["llama3.1:8b"])[0]
            save_config(cfg)
            console.print(f"[green]provider set:[/green] {cfg.provider}/{cfg.model}")

        # IceBerg :: secure  - AI-powered find & browse (bright/dark), incl. the GUI.
        from .secure.cli import build_secure_cli
        app.add_typer(build_secure_cli(console), name="secure")

        return app


MODULE = IceBergModule()
