"""Tool acquisition: discover missing software and install it (confirmed).

When the Cyberdeck's plan needs a tool that is not on the host, this layer finds it:
first in the local catalogs (ShadowDragon's Kali overlay, AirBender's networking
set), then via the full web through Iceberg's bright/dark search. Candidates are
shown to the operator, and installation only ever happens from an OFFICIAL
source (apt, brew, pip) after explicit confirmation. Nothing is auto-downloaded
or auto-run behind the operator's back.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional

from ..host import is_available


@dataclass
class ToolCandidate:
    name: str
    source: str          # 'installed' | 'catalog' | 'web'
    install_command: str
    note: str = ""
    url: str = ""


def _on_noop(_s: str, _m: str) -> None:
    pass


def resolve_tools(tool_names: list[str], *, on_event: Optional[Callable[[str, str], None]] = None) -> dict:
    """For each tool name, return its status + install path.

    Returns {name: {'installed': bool, 'candidate': ToolCandidate|None}}.
    """
    on_event = on_event or _on_noop
    result = {}
    for name in tool_names:
        binary = _binary_name(name)
        if is_available(binary):
            result[name] = {"installed": True, "candidate": None}
            continue
        candidate = _find_candidate(binary, on_event=on_event)
        result[name] = {"installed": False, "candidate": candidate}
    return result


def missing_tools(tool_names: list[str]) -> list[str]:
    """Return the subset of tools that are not installed."""
    return [n for n in tool_names
            if (binary := _binary_name(n)) and not is_available(binary)]


def _binary_name(tool_ref: str) -> str:
    """Normalize a plan tool reference to a host binary name."""
    # 'shadowdragon.kali_run::tshark' -> 'tshark' ; 'airbender.nmap' -> 'nmap'
    if tool_ref == "cyberdeck.report":
        return ""
    if tool_ref == "airbender.chain":
        return "nmap"
    return tool_ref.rsplit("::", 1)[-1].rsplit(".", 1)[-1]


def _find_candidate(binary: str, *, on_event=None) -> Optional[ToolCandidate]:
    """Find an install candidate for a missing binary (catalog first, then web)."""
    on_event = on_event or _on_noop
    cat = _catalog_candidate(binary)
    if cat:
        return cat
    web = _web_candidate(binary, on_event=on_event)
    if web:
        return web
    # Last resort: a best-guess package-manager command.
    return ToolCandidate(
        name=binary, source="guess",
        install_command=f"sudo apt install -y {binary}",
        note=f"No catalog/web match found. Best guess: install '{binary}' via apt.")


def _catalog_candidate(binary: str) -> Optional[ToolCandidate]:
    """Match against the known Kali/networking catalogs for an official package."""
    try:
        from ..platforms.shadowdragon.catalog import KALI_CATALOG
        for tools in KALI_CATALOG.values():
            if binary in tools:
                return ToolCandidate(
                    name=binary, source="catalog",
                    install_command=f"sudo apt install -y {binary}",
                    note=f"'{binary}' is part of the Kali Linux toolset (official apt package).")
    except Exception:
        pass
    networking = {"nmap", "masscan", "arp-scan", "tcpdump", "tshark", "dig", "whois",
                  "traceroute", "netdiscover", "fping"}
    if binary in networking:
        return ToolCandidate(
            name=binary, source="catalog",
            install_command=f"sudo apt install -y {binary}",
            note=f"'{binary}' is a standard networking tool (official package).")
    return None


def _web_candidate(binary: str, *, on_event=None) -> Optional[ToolCandidate]:
    """Search the web (via Iceberg's bright engines) for an install source.

    Returns a candidate describing where to get it - installation still requires
    explicit confirmation and uses an official package manager where possible.
    """
    on_event = on_event or _on_noop
    try:
        from ..platforms.iceberg.secure.engines import BRIGHTSIDE_ENGINES
        from ..platforms.iceberg.secure.search import get_search_results
    except Exception:
        return None
    try:
        on_event("search", f"searching the web for '{binary}' install instructions...")
        hits = get_search_results(f"install {binary} official download linux macos",
                                  mode="bright")
        if not hits:
            return None
        top = hits[0] if isinstance(hits, list) else None
        title = top.get("title", "") if isinstance(top, dict) else str(top)
        url = top.get("url", "") if isinstance(top, dict) else ""
        return ToolCandidate(
            name=binary, source="web",
            install_command=f"sudo apt install -y {binary}  # verify on the official site",
            note=f"Web result: {title[:100]}",
            url=url)
    except Exception:
        return None


def install(candidate: ToolCandidate, *, confirm: Callable[[str], bool] = None,
            runner: Callable[[str], tuple[bool, str]] = None) -> tuple[bool, str]:
    """Install a candidate. Requires explicit confirmation by default.

    Provenance is verified: only known package managers (apt, brew, pip, pipx)
    are executed. Arbitrary download/execute commands (curl|bash, wget, raw
    scripts) are refused outright so the operator never accidentally runs an
    untrusted binary. ``confirm`` defaults to a terminal prompt; ``runner`` is
    injectable for testability.
    """
    verified = verify_provenance(candidate)
    if not verified.ok:
        return False, f"refused: {verified.reason}"
    confirm = confirm or _default_confirm
    prompt = (f"Install '{candidate.name}'?\n  source: {candidate.source}\n"
              f"  command: {candidate.install_command}\n"
              f"  note: {candidate.note}\n"
              f"  provenance: {verified.reason}\n"
              f"Only proceed if you trust the source. Proceed?")
    if not confirm(prompt):
        return False, "installation declined by operator"
    runner = runner or _default_runner
    result = runner(candidate.install_command)
    if result[0]:
        from ..host import which
        which.cache_clear()
    return result


@dataclass
class ProvenanceResult:
    ok: bool
    reason: str


# Package managers we will execute. Anything else (curl|bash, wget, raw scripts)
# is refused so the operator never silently runs an untrusted binary.
_ALLOWED_INSTALLERS = ("apt", "apt-get", "brew", "pip", "pip3", "pipx")


def verify_provenance(candidate: ToolCandidate) -> ProvenanceResult:
    """Check that an install command only uses a known package manager.

    Refuses pipe-to-shell, direct downloads, and any command whose first token
    is not an allowed installer. This is the provenance gate before confirmation.
    """
    cmd = (candidate.install_command or "").strip()
    # Strip a leading sudo.
    tokens = cmd.split()
    if tokens and tokens[0] == "sudo":
        tokens = tokens[1:]
    if not tokens:
        return ProvenanceResult(False, "empty install command")
    installer = tokens[0]
    # Reject pipe-to-shell / direct-download patterns outright.
    joined = " ".join(tokens)
    if any(bad in joined for bad in ("| sh", "|sh", "| bash", "|bash", "curl",
                                     "wget", "http://", "https://", "/tmp/",
                                     "&&", ";")):
        return ProvenanceResult(False,
                                f"refused: command pattern not allowed ({joined[:60]}); "
                                "only package managers are executed")
    if installer not in _ALLOWED_INSTALLERS:
        return ProvenanceResult(False,
                                f"refused: '{installer}' is not an approved package manager "
                                f"(allowed: {', '.join(_ALLOWED_INSTALLERS)})")
    return ProvenanceResult(True, f"verified: {installer} package manager")


def _default_confirm(prompt: str) -> bool:
    from rich.console import Console
    from rich.prompt import Confirm
    return Confirm.ask(prompt, default=False, console=Console())


def _default_runner(command: str) -> tuple[bool, str]:
    import subprocess
    try:
        proc = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=600)
        return proc.returncode == 0, (proc.stdout + proc.stderr)[:2000]
    except Exception as e:
        return False, str(e)
