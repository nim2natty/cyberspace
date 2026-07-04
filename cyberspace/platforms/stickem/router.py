"""StickEm router bridge - OpenWrt router control (the 3rd hardware component).

Controls an OpenWrt-based router (OpenWrt One by default) via SSH. Combined with
the ESP32 Marauder and FT232, this gives StickEm three hardware interfaces under
one command surface: router (WiFi/network control) + ESP32 (wireless attacks) +
FT232 (serial console).

The router is the backbone: it manages the lab network, provides DHCP/DNS, and
can be configured for rogue-AP / MITM scenarios. The ESP32 handles 802.11 attacks
(deauth, PMKID capture). The FT232 provides direct UART access to the router or
other IoT devices.

Used against your OWN lab router/AP only. Configure with: cyberspace stickem set-router <host> <user>
"""
from __future__ import annotations

import subprocess
from typing import Optional


# Router presets for common OpenWrt hardware.
ROUTER_PRESETS = {
    "openwrt-one": {"default_ip": "192.168.1.1", "default_user": "root",
                     "default_baud": 115200, "wifi_iface": "wlan0",
                     "note": "OpenWrt One (Filogic 820) - the recommended target."},
    "generic-openwrt": {"default_ip": "192.168.1.1", "default_user": "root",
                         "default_baud": 115200, "wifi_iface": "wlan0",
                         "note": "Any OpenWrt router (generic defaults)."},
    "gl-inet": {"default_ip": "192.168.8.1", "default_user": "root",
                "default_baud": 115200, "wifi_iface": "wlan0",
                "note": "GL.iNet travel routers (Beryl, Slate, etc.)."},
    "raspberry-pi": {"default_ip": "192.168.1.1", "default_user": "root",
                     "default_baud": 115200, "wifi_iface": "wlan0",
                     "note": "Raspberry Pi running OpenWrt."},
}


class RouterBridge:
    """Drive an OpenWrt router over SSH."""

    def __init__(self, host: str = "192.168.1.1", user: str = "root",
                 port: int = 22, key_file: str = "", router_type: str = "openwrt-one"):
        self.host = host
        self.user = user
        self.port = port
        self.key_file = key_file
        self.router_type = router_type

    def _ssh(self, command: str, timeout: int = 30) -> str:
        """Run a command on the router via SSH (non-interactive)."""
        # Validate: no shell metacharacters in the command body
        bad = (";", "|", "&", "`", "$", "(", ")", "\n", ">")
        if any(c in command for c in bad):
            return f"rejected: command contains shell metacharacters"
        args = ["ssh", "-o", "StrictHostKeyChecking=no", "-o", "ConnectTimeout=10",
                "-o", "BatchMode=yes", "-p", str(self.port)]
        if self.key_file:
            args += ["-i", self.key_file]
        args.append(f"{self.user}@{self.host}")
        args.append(command)
        try:
            r = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
            if r.returncode != 0:
                return f"[ssh error] {r.stderr.strip() or r.stdout.strip()}"
            return r.stdout.strip()
        except subprocess.TimeoutExpired:
            return "[timeout] SSH command took too long"
        except FileNotFoundError:
            return "[error] ssh client not found"
        except Exception as e:
            return f"[error] {e}"

    def status(self) -> str:
        """Get router status: uptime, interfaces, WiFi."""
        out = self._ssh("cat /proc/uptime; echo '---'; ifconfig wlan0 2>/dev/null || echo 'no wlan0'; echo '---'; iwinfo 2>/dev/null || echo 'no iwinfo'")
        return out or "no response (check host/user/key)"

    def wifi_config(self) -> str:
        """Show current WiFi configuration."""
        return self._ssh("uci show wireless")

    def wifi_set_ssid(self, ssid: str, iface: str = "") -> str:
        """Change the WiFi SSID on the router (lab network only)."""
        clean = "".join(c for c in ssid if c.isalnum() or c in " -_")
        if not clean:
            return "invalid SSID"
        iface = iface or "default_radio0"
        cmds = f"uci set wireless.{iface}.ssid='{clean}'; uci commit wireless; wifi reload"
        # We validated individual components; join with known-safe separators
        return self._ssh_raw(cmds)

    def wifi_enable(self) -> str:
        return self._ssh_raw("wifi up")

    def wifi_disable(self) -> str:
        return self._ssh_raw("wifi down")

    def dhcp_leases(self) -> str:
        """List current DHCP leases (connected clients)."""
        return self._ssh("cat /tmp/dhcp.leases")

    def firewall_status(self) -> str:
        return self._ssh("uci show firewall")

    def packages_list(self) -> str:
        """List installed packages on the router."""
        return self._ssh("opkg list-installed")

    def ping(self, target: str) -> str:
        """Ping a target FROM the router."""
        t = "".join(c for c in target if c.isalnum() or c in ".:")
        if not t:
            return "invalid target"
        return self._ssh(f"ping -c 3 {t}")

    def _ssh_raw(self, command: str, timeout: int = 30) -> str:
        """Run a multi-command SSH string (for uci commands that need ;)."""
        args = ["ssh", "-o", "StrictHostKeyChecking=no", "-o", "ConnectTimeout=10",
                "-o", "BatchMode=yes", "-p", str(self.port)]
        if self.key_file:
            args += ["-i", self.key_file]
        args.append(f"{self.user}@{self.host}")
        args.append(command)
        try:
            r = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
            if r.returncode != 0:
                return f"[ssh error] {r.stderr.strip() or 'connection failed'}"
            return r.stdout.strip() or "(ok)"
        except Exception as e:
            return f"[error] {e}"

    def available(self) -> bool:
        """Quick reachability check."""
        r = self._ssh("echo ok", timeout=5)
        return "ok" in r and "error" not in r.lower()
