"""StickEm module - the ESP32 Marauder + FT232 + Router super-tool.

Exposes a unified CLI (`cyberspace stickem ...`) and agent tools so cyberbot can
drive ALL three hardware interfaces in one conversation: ESP32 (wireless attacks),
FT232 (serial console), and the OpenWrt router (network backbone).
"""
from __future__ import annotations

from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from ...modules.base import Module, ModuleInfo, Tool, ToolRegistry
from ...config import ensure_dirs, MODULES_DIR
from .bridge import ConsoleBridge, MarauderBridge, list_ports
from .router import RouterBridge, ROUTER_PRESETS

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


def _router() -> Optional[RouterBridge]:
    st = _load_state()
    host = st.get("router_host")
    if not host:
        return None
    return RouterBridge(host=host, user=st.get("router_user", "root"),
                        port=st.get("router_port", 22),
                        key_file=st.get("router_key", ""),
                        router_type=st.get("router_type", "openwrt-one"))


# --- agent tool functions --------------------------------------------------- #
def _tool_help(**_):
    m = _marauder()
    return "ESP32 port not configured. Run: cyberspace stickem set-esp32 <port>" if not m else m.help()


def _tool_scan(**_):
    m = _marauder()
    return "ESP32 port not configured." if not m else m.scan_ap()


def _tool_select(ssid: str = ""):
    m = _marauder()
    if not m: return "ESP32 port not configured."
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


def _tool_router_status(**_):
    r = _router()
    if not r: return "Router not configured. Run: cyberspace stickem set-router <host>"
    return r.status()


def _tool_router_leases(**_):
    r = _router()
    if not r: return "Router not configured."
    return r.dhcp_leases()


def _tool_hardware_status(**_):
    """Unified status: show all 3 hardware components at once."""
    st = _load_state()
    lines = []
    # ESP32
    esp = st.get("esp32_port", "(not set)")
    lines.append(f"ESP32 Marauder: {esp}")
    # FT232
    ft = st.get("ft232_port", "(not set)")
    lines.append(f"FT232 serial:  {ft}@{st.get('ft232_baud', 115200)}")
    # Router
    rh = st.get("router_host", "(not set)")
    lines.append(f"Router:        {rh} (type={st.get('router_type', 'openwrt-one')})")
    return "\n".join(lines)



class StickEmModule(Module):
    def describe(self) -> ModuleInfo:
        return ModuleInfo(
            name="stickem", display_name="StickEm", version="0.1.0",
            emoji="\U0001f50c",
            description="Super-tool: ESP32 + FT232 + OpenWrt router, unified hardware control.",
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
        registry.register(Tool(
            name="stickem.router_status",
            description="Get OpenWrt router status (uptime, WiFi, interfaces).",
            parameters={"type": "object", "properties": {}}, fn=_tool_router_status))
        registry.register(Tool(
            name="stickem.router_leases",
            description="List DHCP leases (connected clients) on the router.",
            parameters={"type": "object", "properties": {}}, fn=_tool_router_leases))
        registry.register(Tool(
            name="stickem.hardware_status",
            description="Show status of ALL hardware: ESP32 + FT232 + router.",
            parameters={"type": "object", "properties": {}}, fn=_tool_hardware_status))

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

        # --- router (3rd hardware component) ------------------------------ #
        @app.command("set-router")
        def set_router(host: str = typer.Argument(...),
                       user: str = typer.Option("root", "-u"),
                       router_type: str = typer.Option("openwrt-one", "--type",
                            help="openwrt-one|generic-openwrt|gl-inet|raspberry-pi"),
                       port: int = typer.Option(22, "--ssh-port"),
                       key: str = typer.Option("", "--key", help="SSH key file path")):
            """Configure the OpenWrt router connection."""
            st = _load_state()
            st["router_host"] = host; st["router_user"] = user
            st["router_port"] = port; st["router_key"] = key
            st["router_type"] = router_type
            _save_state(st)
            console.print(f"[green]router set:[/green] {user}@{host}:{port} ({router_type})")
            if router_type in ROUTER_PRESETS:
                console.print(f"[dim]{ROUTER_PRESETS[router_type]['note']}[/dim]")

        # Router sub-app
        router_app = typer.Typer(help="OpenWrt router control.")
        app.add_typer(router_app, name="router")

        @router_app.command("status")
        def _rstatus():
            """Router status: uptime, WiFi, interfaces."""
            r = _router()
            if not r: console.print("[red]router not set. Run: cyberspace stickem set-router <host>[/red]"); return
            console.print(r.status())

        @router_app.command("wifi")
        def _rwifi():
            """Show WiFi config."""
            r = _router()
            if not r: console.print("[red]router not set.[/red]"); return
            console.print(r.wifi_config())

        @router_app.command("leases")
        def _rleases():
            """List DHCP leases (connected clients)."""
            r = _router()
            if not r: console.print("[red]router not set.[/red]"); return
            console.print(r.dhcp_leases())

        @router_app.command("set-ssid")
        def _rssid(ssid: str = typer.Argument(...)):
            """Change the WiFi SSID on the router (lab network only)."""
            r = _router()
            if not r: console.print("[red]router not set.[/red]"); return
            console.print(r.wifi_set_ssid(ssid))

        @router_app.command("ping")
        def _rping(target: str = typer.Argument(...)):
            """Ping a target FROM the router."""
            r = _router()
            if not r: console.print("[red]router not set.[/red]"); return
            console.print(r.ping(target))

        @router_app.command("packages")
        def _rpkgs():
            """List installed packages on the router."""
            r = _router()
            if not r: console.print("[red]router not set.[/red]"); return
            console.print(r.packages_list())

        # --- unified hardware status --------------------------------------- #
        @app.command("hardware")
        def hardware():
            """Show ALL hardware: ESP32 + FT232 + Router status."""
            console.print(Panel.fit(_tool_hardware_status(), title="StickEm hardware", border_style="cyan"))

        return app


MODULE = StickEmModule()
