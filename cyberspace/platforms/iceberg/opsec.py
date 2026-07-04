"""System-level OPSEC helpers (the 'system' half of IceBerg).

Wraps common host-level privacy/OPSEC tools: macchanger, tor/proxychains,
hostname rotation, and a self-check. Used against your OWN lab only.
"""
from __future__ import annotations

from ...host import is_available, missing_hint, run


def rotate_mac(interface: str = "eth0") -> str:
    """Randomize the MAC address on an interface (requires root + macchanger)."""
    if not is_available("macchanger"):
        return missing_hint("macchanger")
    return run("macchanger", ["-r", interface], timeout=30).text()


def set_hostname(name: str) -> str:
    """Set a non-identifying hostname for the session."""
    import subprocess
    try:
        subprocess.run(["hostname", name], check=True)
        return f"hostname set to {name}"
    except Exception as e:
        return f"could not set hostname: {e}"


def tor_status() -> str:
    if not is_available("tor"):
        return missing_hint("tor")
    return run("systemctl", ["is-active", "tor"], timeout=10).text()


def proxychains_check() -> str:
    if not is_available("proxychains"):
        return missing_hint("proxychains")
    return "proxychains available - run tools through: proxychains <tool>"


def selfcheck() -> str:
    """Quick local OPSEC posture readout (no network calls)."""
    import socket
    lines = ["OPSEC self-check:"]
    for tool in ("macchanger", "tor", "proxychains", "macchanger"):
        lines.append(f"  {tool}: {'installed' if is_available(tool) else 'MISSING'}")
    try:
        host = socket.gethostname()
        lines.append(f"  hostname: {host}  (rotate with: iceberg set-hostname <name>)")
    except Exception:
        pass
    return "\n".join(lines)
