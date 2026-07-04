"""Tor control + health for the IceBerg :: e tool (darkside mode).

Tor speaks SOCKS5 on :9050 (proxy) and a control protocol on :9051. We need:
  - a reachability check (is the SOCKS proxy up?)
  - a "new identity" (NEWNYM) so each investigation uses a fresh circuit, and
  - a SOCKS URL string the search/scrape clients consume.

socks5h:// means the *proxy* (Tor) resolves the hostname - critical for .onion,
which the local resolver cannot resolve.
"""
from __future__ import annotations

import socket
from typing import Optional

DEFAULT_SOCKS_PORT = 9050
DEFAULT_CONTROL_PORT = 9051


def _can_connect(host: str, port: int, timeout: float = 2.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def tor_available(socks_host: str = "127.0.0.1", socks_port: int = DEFAULT_SOCKS_PORT) -> bool:
    """True if a Tor SOCKS proxy is listening (i.e. `service tor` is up)."""
    return _can_connect(socks_host, socks_port)


def socks_url(host: str = "127.0.0.1", port: int = DEFAULT_SOCKS_PORT) -> str:
    """The SOCKS5h proxy URL (remote DNS resolution, required for .onion)."""
    return f"socks5h://{host}:{port}"


def new_identity(host: str = "127.0.0.1", control_port: int = DEFAULT_CONTROL_PORT,
                 password: Optional[str] = None) -> tuple[bool, str]:
    """Send NEWNYM to the Tor control port to get a fresh exit/circuit.

    Returns (ok, message). Requires ControlPort + (optionally) HashedControlPassword
    in the torrc. If auth fails or the port is closed, returns a clear message.
    """
    try:
        with socket.create_connection((host, control_port), timeout=5.0) as s:
            f = s.makefile("rwb", buffering=0)
            greet = f.readline().decode(errors="replace").strip()
            # Authenticate. Empty cookie / no auth: send zero-length hex.
            if password:
                f.write(f'AUTHENTICATE "{password}"\r\n'.encode())
            else:
                f.write(b'AUTHENTICATE ""\r\n')
            auth = f.readline().decode(errors="replace").strip()
            if not auth.startswith("250"):
                return False, f"control auth rejected: {auth}"
            f.write(b"SIGNAL NEWNYM\r\n")
            res = f.readline().decode(errors="replace").strip()
            if res.startswith("250"):
                return True, "new identity requested (NEWNYM accepted)"
            return False, f"NEWNYM rejected: {res}"
    except OSError as e:
        return False, f"cannot reach Tor control port {host}:{control_port} - {e}"
    except Exception as e:  # malformed greeting etc.
        return False, f"control protocol error: {e}"
