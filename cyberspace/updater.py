"""Installation-aware, integrity-preserving Cyberspace software updates."""
from __future__ import annotations

import hashlib
import os
import platform
import subprocess
import sys
import tempfile
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Callable


REPOSITORY = "nim2natty/cyberspace"


@dataclass(frozen=True)
class UpdateResult:
    ok: bool
    method: str
    message: str


def installation_method(root: Path | None = None) -> str:
    if getattr(sys, "frozen", False):
        return "standalone"
    root = root or _source_root()
    if (root / ".git").exists() and (root / "pyproject.toml").exists():
        return "source"
    return "python-package"


def update_latest(*, root: Path | None = None, force: bool = False,
                  runner: Callable = subprocess.run,
                  downloader: Callable | None = None) -> UpdateResult:
    """Update using the current installation method; never execute remote scripts."""
    root = (root or _source_root()).resolve()
    method = installation_method(root)
    if method == "source":
        return _update_source(root, force=force, runner=runner)
    if method == "standalone":
        return _update_standalone(downloader=downloader)
    command = [sys.executable, "-m", "pip", "install", "--upgrade",
               f"git+https://github.com/{REPOSITORY}.git"]
    result = runner(command, capture_output=True, text=True)
    return UpdateResult(result.returncode == 0, method,
                        _result_message(result, "Python package updated"))


def _update_source(root: Path, *, force: bool, runner: Callable) -> UpdateResult:
    status = runner(["git", "-C", str(root), "status", "--porcelain"],
                    capture_output=True, text=True)
    if status.returncode != 0:
        return UpdateResult(False, "source", _result_message(status, "git status failed"))
    if status.stdout.strip() and not force:
        return UpdateResult(False, "source",
                            "Update refused: the source checkout has uncommitted changes. "
                            "Commit/stash them, or rerun with --force to preserve them while "
                            "attempting a fast-forward update.")
    pull = runner(["git", "-C", str(root), "pull", "--ff-only", "origin", "main"],
                  capture_output=True, text=True)
    if pull.returncode != 0:
        return UpdateResult(False, "source", _result_message(pull, "git update failed"))
    python = root / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    if not python.exists():
        python = Path(sys.executable)
    install = runner([str(python), "-m", "pip", "install", "-e", str(root)],
                     capture_output=True, text=True)
    return UpdateResult(install.returncode == 0, "source",
                        _result_message(install, "Source checkout updated and environment refreshed"))


def _update_standalone(*, downloader: Callable | None = None) -> UpdateResult:
    os_name = {"Darwin": "macos", "Linux": "linux", "Windows": "windows"}.get(
        platform.system())
    arch = {"x86_64": "x86_64", "AMD64": "x86_64", "arm64": "arm64",
            "aarch64": "arm64"}.get(platform.machine())
    if not os_name or not arch:
        return UpdateResult(False, "standalone", "No standalone release for this OS/architecture")
    suffix = ".exe" if os_name == "windows" else ""
    asset = f"cyberspace-{os_name}-{arch}{suffix}"
    base = f"https://github.com/{REPOSITORY}/releases/latest/download"
    fetch = downloader or _download
    with tempfile.TemporaryDirectory(prefix="cyberspace-update-") as tmp:
        binary = Path(tmp) / asset
        checksum = Path(tmp) / f"{asset}.sha256"
        try:
            fetch(f"{base}/{asset}", binary)
            fetch(f"{base}/{asset}.sha256", checksum)
        except Exception as exc:
            return UpdateResult(False, "standalone", f"Download failed: {exc}")
        expected = checksum.read_text().split()[0].lower()
        actual = hashlib.sha256(binary.read_bytes()).hexdigest()
        if actual != expected:
            return UpdateResult(False, "standalone", "Release checksum verification failed")
        destination = Path(sys.executable)
        if os.name == "nt":
            return UpdateResult(False, "standalone",
                                "Close Cyberspace and rerun installer/install.ps1 to replace the active executable")
        binary.chmod(0o755)
        os.replace(binary, destination)
    return UpdateResult(True, "standalone", f"Standalone executable updated: {destination}")


def _download(url: str, destination: Path) -> None:
    request = urllib.request.Request(url, headers={"User-Agent": "cyberspace-updater"})
    with urllib.request.urlopen(request, timeout=60) as response:
        destination.write_bytes(response.read())


def _source_root() -> Path:
    return Path(os.environ.get("CYBERSPACE_ROOT", Path(__file__).resolve().parents[1]))


def _result_message(result, success: str) -> str:
    output = ((getattr(result, "stdout", "") or "") +
              (getattr(result, "stderr", "") or "")).strip()
    return success + (f"\n{output[-2000:]}" if output else "")