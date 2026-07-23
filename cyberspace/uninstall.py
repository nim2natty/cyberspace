"""Safe removal helpers for the launcher, environment, source, and user data."""
from __future__ import annotations

import shutil
import os
import subprocess
import sys
from pathlib import Path

MANAGED_MARKER = "# Managed by cyberspace installer."


def remove_installation(root: Path, launcher: Path, data_dir: Path, *,
                        remove_source: bool = False, purge_data: bool = False,
                        standalone: bool = False, deferred_remover=None) -> list[str]:
    """Remove an installation and return human-readable actions performed."""
    root = root.resolve()
    actions: list[str] = []
    if launcher.exists() and standalone:
        # A frozen executable must remain at its launch path until its bootloader
        # exits. Immediate unlinking makes PyInstaller abort with "moved or deleted
        # since this application was launched" on Linux and macOS; Windows locks it.
        (deferred_remover or _schedule_executable_removal)(launcher)
        actions.append(f"scheduled executable removal {launcher}")
    elif launcher.exists():
        try:
            managed = MANAGED_MARKER in launcher.read_text(errors="ignore")
        except OSError:
            managed = False
        if managed:
            launcher.unlink()
            actions.append(f"removed launcher {launcher}")
        else:
            actions.append(f"kept unmanaged launcher {launcher}")

    venv = root / ".venv"
    if venv.is_dir():
        shutil.rmtree(venv)
        actions.append(f"removed environment {venv}")

    if purge_data and data_dir.exists():
        shutil.rmtree(data_dir)
        actions.append(f"removed user data {data_dir}")

    if remove_source and root.is_dir():
        # Refuse obviously dangerous roots even if supplied programmatically.
        if root == Path(root.anchor) or root == Path.home().resolve():
            raise ValueError(f"refusing to remove unsafe source path: {root}")
        if not (root / "pyproject.toml").is_file() or not (root / "cyberspace" / "__init__.py").is_file():
            raise ValueError(f"refusing to remove unrecognized source path: {root}")
        shutil.rmtree(root)
        actions.append(f"removed source {root}")
    return actions


def _schedule_executable_removal(launcher: Path, *, popen=subprocess.Popen,
                                 platform_name: str = os.name) -> None:
    """Start a detached helper which removes a frozen executable after exit."""
    launcher = launcher.resolve()
    common = {"stdin": subprocess.DEVNULL, "stdout": subprocess.DEVNULL,
              "stderr": subprocess.DEVNULL, "close_fds": True}
    if platform_name == "nt":
        command = ["cmd", "/c",
                   f'ping 127.0.0.1 -n 3 >NUL & del /f /q "{launcher}"']
        popen(command, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0), **common)
    else:
        # Delay long enough for the PyInstaller parent bootloader to finish after
        # the Python child exits. Pass the path as an argument, never shell text.
        command = ["sh", "-c", 'sleep 2; rm -f -- "$1"', "cyberspace-uninstall",
                   str(launcher)]
        popen(command, start_new_session=True, **common)