"""Shared helpers for running host CLI tools safely.

Every platform wraps real tools (nmap, sqlmap, etc.). This module gives them a
consistent, safe runner that: resolves the binary, enforces a timeout, captures
output, and never silently hides errors. Designed so the agent gets clean text
back from every tool call.
"""
from __future__ import annotations

import shlex
import shutil
import subprocess
import os
import platform
from pathlib import Path
from dataclasses import dataclass
from functools import lru_cache
from typing import Optional


_ELEVATED = False
_ELEVATABLE = frozenset({
    "nmap", "masscan", "netdiscover", "arp-scan", "tcpdump", "tshark",
    "airmon-ng", "airodump-ng", "aireplay-ng", "airbase-ng", "macchanger",
})


@dataclass
class RunResult:
    ok: bool
    stdout: str
    stderr: str
    returncode: int

    def text(self) -> str:
        if self.ok:
            return self.stdout.strip() or "(no output)"
        return f"[exit {self.returncode}] {self.stderr.strip() or self.stdout.strip()}"


@lru_cache(maxsize=128)
def which(name: str) -> Optional[str]:
    """Resolve a host binary once per process.

    PATH does not normally change during a cyberspace command.  Acquisition clears
    this cache after installing software, avoiding repeated filesystem searches in
    plans which invoke or inspect the same binary several times.
    """
    return shutil.which(name)


def is_available(name: str) -> bool:
    return which(name) is not None


def missing_hint(name: str, pkg: Optional[str] = None) -> str:
    pkg = pkg or name
    return (f"tool '{name}' is not installed. Install it with: "
            f"sudo apt install {pkg}  (or: cyberspace doctor --install)")


def runtime_environment() -> dict:
    """Return facts about where host tools really execute."""
    container = (Path("/.dockerenv").exists() or Path("/run/.containerenv").exists()
                 or bool(os.environ.get("container")))
    admin = (os.name == "nt" and _windows_admin()) or (
        os.name != "nt" and getattr(os, "geteuid", lambda: -1)() == 0)
    return {"os": platform.system(), "container": container,
            "admin": bool(admin), "elevation_enabled": _ELEVATED}


def runtime_summary() -> str:
    env = runtime_environment()
    location = "container network namespace" if env["container"] else "native host network"
    privilege = "administrator/root" if env["admin"] else (
        "confirmed elevation" if env["elevation_enabled"] else "current user")
    return f"Runtime: {env['os']}, {location}, privileges={privilege}."


def enable_elevation(confirm=None, runner=None) -> tuple[bool, str]:
    """Authenticate an allowlisted per-command elevation session."""
    global _ELEVATED
    env = runtime_environment()
    if env["container"]:
        return False, ("Cyberspace is inside a container. sudo cannot escape its network namespace. "
                       "Restart it with host networking and required capabilities (for Docker on "
                       "Linux: --network host --cap-add NET_RAW --cap-add NET_ADMIN).")
    if env["admin"]:
        _ELEVATED = True
        return True, "already running with administrator/root privileges"
    if os.name == "nt":
        return False, ("Restart the terminal with 'Run as administrator'; Windows cannot elevate "
                       "an already-running CLI session safely.")
    if not is_available("sudo"):
        return False, "sudo is not installed; run from an administrator/root shell"
    if confirm is None:
        return False, "explicit operator confirmation is required to enable elevation"
    if not confirm("Allow Cyberspace to elevate reviewed network/capture binaries for this session?"):
        return False, "elevation declined by operator"
    authenticate = runner or (lambda argv: subprocess.run(argv).returncode)
    if authenticate([which("sudo") or "sudo", "-v"]) != 0:
        return False, "sudo authentication failed"
    _ELEVATED = True
    return True, "elevation enabled for allowlisted host tools only"


def disable_elevation() -> None:
    global _ELEVATED
    _ELEVATED = False


def _windows_admin() -> bool:
    try:
        import ctypes
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def run(name: str, args: list[str], timeout: int = 300,
        input_text: Optional[str] = None) -> RunResult:
    """Run a host tool by name + args. Returns a RunResult.

    Security: `name` is resolved via PATH; `args` is a list
    (never a shell string) so there's no shell injection. Callers must validate
    any operator-supplied values before passing them here.
    """
    bin_path = which(name)
    if not bin_path:
        return RunResult(False, "", missing_hint(name), 127)
    try:
        command = [bin_path, *args]
        if _ELEVATED and name in _ELEVATABLE and os.name != "nt" and not runtime_environment()["admin"]:
            command = [which("sudo") or "sudo", "-n", *command]
        proc = subprocess.run(
            command,
            capture_output=True, text=True, timeout=timeout, input=input_text,
        )
        return RunResult(proc.returncode == 0, proc.stdout, proc.stderr, proc.returncode)
    except subprocess.TimeoutExpired:
        return RunResult(False, "", f"timed out after {timeout}s", -1)
    except Exception as e:
        return RunResult(False, "", str(e), 1)


def quote(value: str) -> str:
    return shlex.quote(value)
