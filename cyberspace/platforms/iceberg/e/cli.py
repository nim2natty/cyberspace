"""CLI for the IceBerg :: e tool (brightside / darkside AI find & browse).

Exposed as:   cyberspace iceberg e <command>

  e config   interactive security wizard (set Tor posture before browsing)
  e find     headless AI find: refine -> search -> filter -> scrape -> summarize
  e browse   open a URL in the IceBerg browser (Tor-routed for darkside)
  e gui      launch the Streamlit graphic interface
  e status   Tor health + saved security config + python dependency check
"""
from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.table import Table

from .intel import PRESET_LABELS
from .pipeline import run_find, save_investigation
from .security import PRESETS, SecurityConfig, dark_settings
from .tor import new_identity, tor_available


def _check_dep(name: str) -> bool:
    return importlib.util.find_spec(name) is not None


def build_e_cli(console: Console) -> typer.Typer:
    app = typer.Typer(help="IceBerg :: e - AI-powered find & browse (bright/dark).")

    @app.command("status")
    def status():
        """Show Tor health, saved security config, and python dependencies."""
        sec = SecurityConfig.load()
        t = Table("component", "state", "detail")
        t.add_row("mode", sec.mode, "darkside (Tor)" if sec.mode == "dark"
                  else PRESETS["bright"]["label"])
        tor_ok = tor_available(sec.tor_socks_host, sec.tor_socks_port)
        t.add_row("Tor SOCKS", "[green]reachable[/green]" if tor_ok else "[red]not running[/red]",
                  f"{sec.tor_socks_host}:{sec.tor_socks_port}")
        for dep in ("requests", "bs4", "socks", "streamlit"):
            ok = _check_dep(dep)
            t.add_row(f"py/{dep}", "[green]ok[/green]" if ok else "[red]missing[/red]",
                      "" if ok else "pip install " + dep)
        console.print(t)
        if sec.mode == "dark":
            console.print("\n[bold]Dark posture:[/bold]")
            for line in dark_settings(sec):
                console.print("  " + line)
        console.print("\n[dim]cyberbot LLM powers the find/summarize step - "
                      "configure with: cyberspace setup[/dim]")

    # --- config wizard -----------------------------------------------------
    @app.command("config")
    def config():
        """Configure the security posture. Set BEFORE darkside browsing."""
        console.print(Panel.fit(
            "[bold cyan]IceBerg :: e[/bold cyan] - security configuration\n"
            "[dim]Brightside = clearnet. Darkside = Tor + hardening. Pick a preset, "
            "then tune. Dark mode changes transport, DNS, and WebRTC posture.[/dim]",
            border_style="cyan"))
        opts = {str(i): k for i, k in enumerate(PRESETS.keys())}
        t = Table("#", "preset")
        for i, k in enumerate(PRESETS.keys()):
            t.add_row(str(i), PRESETS[k]["label"])
        console.print(t)
        choice = Prompt.ask("Choose preset", choices=list(opts), default="0")
        sec = PRESETS[opts[choice]]["config"]

        if sec.mode == "dark":
            console.print("\n[bold]Darkside tuning[/bold] (Enter keeps default):")
            sec.tor_socks_port = int(Prompt.ask("Tor SOCKS port", default=str(sec.tor_socks_port)))
            sec.tor_control_port = int(Prompt.ask("Tor control port", default=str(sec.tor_control_port)))
            sec.tor_control_password = Prompt.ask("Tor control password (blank=none)",
                                                   default=sec.tor_control_password or "")
            sec.new_identity_per_session = Confirm.ask(
                "Request a NEW Tor identity each run?", default=sec.new_identity_per_session)
            sec.doh_provider = Prompt.ask("DoH provider", default=sec.doh_provider,
                                          choices=["mullvad", "cloudflare", "quad9", "google"])
        else:
            prof = Prompt.ask("IceBerg fingerprint profile for bright browsing "
                              "(blank=default persona)", default=sec.bright_profile or "")
            sec.bright_profile = prof or None

        sec.max_results = int(Prompt.ask("Max search results", default=str(sec.max_results)))
        sec.max_scrape = int(Prompt.ask("Max pages to scrape", default=str(sec.max_scrape)))
        sec.save()
        body = ("\n".join("  " + l for l in dark_settings(sec)) if sec.mode == "dark"
                else "  clearnet, DoH on, WebRTC blocked, UA rotation on")
        console.print(Panel.fit(
            f"[green]Saved.[/green] mode: [bold]{sec.mode}[/bold]\n" + body,
            border_style="green"))
        if sec.mode == "dark" and not tor_available(sec.tor_socks_host, sec.tor_socks_port):
            console.print("[yellow]Tor isn't running yet. Start it before darkside "
                          "browsing: 'service tor start' / 'brew services start tor'.[/yellow]")

    # --- find (headless pipeline) -----------------------------------------
    @app.command("find")
    def find(query: str = typer.Argument(...),
             mode: str = typer.Option("", "--mode", "-m", help="bright|dark"),
             preset: str = typer.Option("general", "--preset", "-p"),
             custom: str = typer.Option("", "--focus", help="extra focus for summary"),
             save: bool = typer.Option(True, "--save/--no-save")):
        """Run the AI find pipeline and print the investigation summary."""
        sec = SecurityConfig.load()
        if mode in ("bright", "dark"):
            sec.mode = mode
        if sec.mode == "dark":
            if not tor_available(sec.tor_socks_host, sec.tor_socks_port):
                console.print(f"[red]Darkside needs Tor at {sec.socks_url()}, which is not "
                              f"running.[/red] Start it, or use --mode bright. "
                              f"Run 'cyberspace iceberg e config' first.")
                raise typer.Exit(1)
            if sec.new_identity_per_session:
                ok, info = new_identity(sec.tor_control_host, sec.tor_control_port,
                                        sec.tor_control_password or None)
                console.print(f"[cyan]tor[/cyan] {info}")

        def on_event(stage, msg):
            console.print(f"[dim]{stage:>8}[/dim]  {msg}")

        inv = run_find(query, sec=sec, preset=preset, custom=custom, on_event=on_event)
        if save and inv.summary and not inv.summary.startswith("[blocked]"):
            save_investigation(inv)
            console.print(f"[dim]saved: {inv.saved_path}[/dim]")
        console.print(Panel.fit(f"[bold]Findings[/bold]  ({inv.refined})", border_style="cyan"))
        console.print(inv.summary)

    # --- browse (IceBerg browser, Tor-routed for dark) --------------------
    @app.command("browse")
    def browse(url: str = typer.Argument(...),
               mode: str = typer.Option("", "--mode", "-m", help="bright|dark"),
               profile: str = typer.Option("", "--profile", "-p")):
        """Open a URL in the IceBerg anti-detect browser (Tor-routed for darkside)."""
        from ..profiles import FingerprintProfile
        sec = SecurityConfig.load()
        if mode in ("bright", "dark"):
            sec.mode = mode
        if profile and profile in FingerprintProfile.list_names():
            p = FingerprintProfile.load(profile)
        else:
            p = FingerprintProfile.from_persona("e-session", "win-chrome")
        if sec.mode == "dark":
            if not tor_available(sec.tor_socks_host, sec.tor_socks_port):
                console.print(f"[red]Darkside needs Tor at {sec.socks_url()}.[/red]")
                raise typer.Exit(1)
            p.proxy = f"socks5://{sec.tor_socks_host}:{sec.tor_socks_port}"
            console.print(f"[cyan]tor[/cyan] routing browser via {p.proxy}")
        from ..browser import launch
        launch(p, url=url, headless=False, console=console)

    # --- gui (Streamlit) --------------------------------------------------
    @app.command("gui")
    def gui(port: int = typer.Option(8501, "--port")):
        """Launch the Streamlit graphic interface."""
        if not _check_dep("streamlit"):
            console.print("[red]streamlit is not installed.[/red] Install the GUI extra:\n"
                          "  pip install 'cyberspace[gui]'   (or: pip install streamlit)")
            raise typer.Exit(1)
        gui_file = Path(__file__).resolve().parent / "gui.py"
        console.print(Panel.fit(
            f"[bold cyan]IceBerg :: e[/bold cyan] GUI starting at "
            f"http://localhost:{port}\n[dim]Ctrl-C to stop.[/dim]", border_style="cyan"))
        subprocess.run([sys.executable, "-m", "streamlit", "run", str(gui_file),
                        "--server.port", str(port), "--server.headless", "true"])

    return app


