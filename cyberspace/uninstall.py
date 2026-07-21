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
                        standalone: bool = False) -> list[str]:
    """Remove an installation and return human-readable actions performed."""
    root = root.resolve()
    actions: list[str] = []
    if launcher.exists() and standalone:
        if os.name == "nt" and launcher.resolve() == Path(sys.executable).resolve():
            # Windows locks a running executable; delete it just after this process exits.
            subprocess.Popen(["cmd", "/c", f'ping 127.0.0.1 -n 2 >NUL & del /f /q "{launcher}"'],
                             creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            actions.append(f"scheduled executable removal {launcher}")
        else:
            launcher.unlink()
            actions.append(f"removed executable {launcher}")
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