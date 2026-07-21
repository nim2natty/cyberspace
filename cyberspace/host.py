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
from dataclasses import dataclass
from typing import Optional


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


def which(name: str) -> Optional[str]:
    return shutil.which(name)


def is_available(name: str) -> bool:
    return which(name) is not None


def missing_hint(name: str, pkg: Optional[str] = None) -> str:
    pkg = pkg or name
    return (f"tool '{name}' is not installed. Install it with: "
            f"sudo apt install {pkg}  (or: cyberspace doctor --install)")


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
        proc = subprocess.run(
            [bin_path, *args],
            capture_output=True, text=True, timeout=timeout, input=input_text,
        )
        return RunResult(proc.returncode == 0, proc.stdout, proc.stderr, proc.returncode)
    except subprocess.TimeoutExpired:
        return RunResult(False, "", f"timed out after {timeout}s", -1)
    except Exception as e:
        return RunResult(False, "", str(e), 1)


def quote(value: str) -> str:
    return shlex.quote(value)
