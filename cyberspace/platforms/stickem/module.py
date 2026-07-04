"""StickEm module - the ESP32 Marauder + FT232 platform.

Exposes both its own CLI (`cyberspace stickem ...`) and agent tools so the
Cyberbot agent can drive wireless attacks and serial consoles in conversation.
"""
from __future__ import annotations

from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from ...modules.base import Module, ModuleInfo, Tool, ToolRegistry
from ...config import ensure_dirs, MODULES_DIR
from .bridge import ConsoleBridge, MarauderBridge, list_ports

console = Console()
STATE = MODULES_DIR / "stickem.json"


def _load_state() -> dict:
    ensure_dirs()
    if not STATE.exists():
        return {}
    import json
    return json.loads(STATE.read_text())


def _save_state(d: dict) -> None:
    ensure_dirs()
    import json
    STATE.write_text(json.dumps(d, indent=2))


def _marauder() -> Optional[MarauderBridge]:
    st = _load_state()
    port = st.get("esp32_port")
    if not port:
        return None
    return MarauderBridge(port=port)


# --- agent tool functions --------------------------------------------------- #
def _tool_help(**_):
    m = _marauder()
    if not m:
        return "ESP32 port not configured. Run: cyberspace stickem set-esp32 <port>"
    return m.help()


def _tool_scan(**_):
    m = _marauder()
    return "ESP32 port not configured." if not m else m.scan_ap()


def _tool_select(ssid: str = ""):
    m = _marauder()
    if not m:
        return "ESP32 port not configured."
    return "ssid required." if not ssid else m.select_ssid(ssid)


def _tool_deauth(count: int = 50):
    m = _marauder()
    return "ESP32 port not configured." if not m else m.deauth(count)


def _tool_sniff(**_):
    m = _marauder()
    return "ESP32 port not configured." if not m else m.sniff_pmkid()


def _tool_ports(**_):
    ports = list_ports()
    return ", ".join(ports) if ports else "no serial ports found"


class StickEmModule(Module):
    def describe(self) -> ModuleInfo:
        return ModuleInfo(
            name="stickem", display_name="StickEm", version="0.1.0",
            emoji="\U0001f50c",
            description="ESP32 Marauder + FT232 hardware bridge (wireless + serial).",
            requires_tools=["pyserial"],
        )

    def register_tools(self, registry: ToolRegistry) -> None:
        registry.register(Tool(
            name="stickem.help",
            description="Show available Marauder commands on the connected ESP32.",
            parameters={"type": "object", "properties": {}}, fn=_tool_help))
        registry.register(Tool(
            name="stickem.scan_ap",
            description="Scan for nearby 2.4GHz access points via the ESP32 Marauder.",
            parameters={"type": "object", "properties": {}}, fn=_tool_scan))
        registry.register(Tool(
            name="stickem.select_ssid",
            description="Select a target SSID on the ESP32 by name (network you own only).",
            parameters={"type": "object",
                        "properties": {"ssid": {"type": "string"}},
                        "required": ["ssid"]}, fn=_tool_select))
        registry.register(Tool(
            name="stickem.deauth",
            description="Send deauth frames (802.11) at the selected SSID. Lab use only.",
            parameters={"type": "object",
                        "properties": {"count": {"type": "integer", "default": 50}}},
            fn=_tool_deauth))
        registry.register(Tool(
            name="stickem.sniff_pmkid",
            description="Capture PMKID/EAPOL frames for offline cracking of an owned lab SSID.",
            parameters={"type": "object", "properties": {}}, fn=_tool_sniff))
        registry.register(Tool(
            name="stickem.list_ports",
            description="List available serial ports (ESP32 / FT232).",
            parameters={"type": "object", "properties": {}}, fn=_tool_ports))

    def build_cli(self) -> typer.Typer:
        app = typer.Typer(help="StickEm: ESP32 Marauder + FT232 hardware bridge.")

        @app.command("ports")
        def ports():
            """List serial ports."""
            ps = list_ports()
            t = Table("port")
            for p in ps:
                t.add_row(p)
            console.print(t or "[dim]no ports found[/dim]")

        @app.command("set-esp32")
        def set_esp32(port: str = typer.Argument(...)):
            """Set the ESP32 (Marauder) serial port."""
            st = _load_state(); st["esp32_port"] = port; _save_state(st)
            console.print(f"[green]ESP32 port set to[/green] {port}")

        @app.command("set-ft232")
        def set_ft232(port: str = typer.Argument(...), baud: int = typer.Option(115200)):
            """Set the FT232 serial console port."""
            st = _load_state(); st["ft232_port"] = port; st["ft232_baud"] = baud
            _save_state(st)
            console.print(f"[green]FT232 set to[/green] {port}@{baud}")

        @app.command("marauder")
        def marauder(cmd: str = typer.Argument("help", help="Marauder command")):
            """Send a raw Marauder command to the ESP32."""
            m = _marauder()
            if not m:
                console.print("[red]ESP32 port not set. Run: cyberspace stickem set-esp32 <port>[/red]")
                raise typer.Exit(1)
            console.print(m.send(cmd))

        @app.command("console")
        def console_cmd():
            """Open an interactive serial console on the FT232."""
            st = _load_state()
            port = st.get("ft232_port")
            if not port:
                console.print("[red]FT232 port not set. Run: cyberspace stickem set-ft232 <port>[/red]")
                raise typer.Exit(1)
            ConsoleBridge(port=port, baudrate=st.get("ft232_baud", 115200)).open_console()

        return app


MODULE = StickEmModule()
