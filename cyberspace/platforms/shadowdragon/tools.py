"""ShadowDragon tool functions (agent-callable wrappers around Kali tools).

Curated wrappers validate input and use the safe host runner (no shell
injection). The generic kali_run lets cyberbot invoke ANY Kali tool by name,
so ShadowDragon truly covers all non-networking Kali tools.
"""
from __future__ import annotations

import shlex

from ...host import is_available, missing_hint, run

_BAD = (";", "|", "&", "`", "$", "(", ")", "\n", "\r", ">", "<")


def _clean(value) -> str:
    if value is None:
        return ""
    return "".join(c for c in str(value) if c not in _BAD).strip()


def _check_url(url) -> str | None:
    if not url or not str(url).startswith(("http://", "https://")):
        return "url must start with http:// or https://"
    if any(c in url for c in _BAD):
        return "invalid characters in url"
    return None


# --- web / vuln ----------------------------------------------------------- #
def sqlmap(url="http://localhost", level=1, risk=1, extra=""):
    if not is_available("sqlmap"):
        return missing_hint("sqlmap")
    err = _check_url(url)
    if err:
        return err
    args = ["-u", url, "--batch", f"--level={int(level)}", f"--risk={int(risk)}"]
    if extra:
        args += [a for a in shlex.split(extra) if not any(c in a for c in _BAD)]
    return run("sqlmap", args, timeout=300).text()


def gobuster(url="http://localhost", wordlist="/usr/share/wordlists/dirb/common.txt"):
    if not is_available("gobuster"):
        return missing_hint("gobuster")
    err = _check_url(url)
    if err:
        return err
    return run("gobuster", ["dir", "-u", url, "-w", wordlist, "-q"], timeout=300).text()


def whatweb(url="http://localhost"):
    if not is_available("whatweb"):
        return missing_hint("whatweb")
    err = _check_url(url)
    if err:
        return err
    return run("whatweb", [url], timeout=120).text()


def nikto(url="http://localhost"):
    if not is_available("nikto"):
        return missing_hint("nikto")
    err = _check_url(url)
    if err:
        return err
    return run("nikto", ["-h", url, "-ask", "no"], timeout=600).text()


def searchsploit(query=""):
    if not is_available("searchsploit"):
        return missing_hint("searchsploit", "exploitdb")
    q = _clean(query)
    if not q:
        return "query required"
    return run("searchsploit", ["--color", q], timeout=120).text()


# --- password cracking ---------------------------------------------------- #
def john(hashfile="", wordlist="/usr/share/wordlists/rockyou.txt"):
    if not is_available("john"):
        return missing_hint("john")
    hf = _clean(hashfile)
    if not hf:
        return "hashfile path required"
    return run("john", ["--wordlist=" + _clean(wordlist), hf], timeout=300).text()


def hashcat(hash="", mode=0, wordlist="/usr/share/wordlists/rockyou.txt"):
    if not is_available("hashcat"):
        return missing_hint("hashcat")
    h = _clean(hash)
    if not h:
        return "hash value required"
    return run("hashcat", ["-m", str(int(mode)), h, _clean(wordlist), "--force"], timeout=300).text()


def hydra(target="", service="ssh", users="/usr/share/wordlists/dirb/common.txt", passwords="/usr/share/wordlists/rockyou.txt"):
    if not is_available("hydra"):
        return missing_hint("hydra")
    t = _clean(target)
    if not t:
        return "target required"
    return run("hydra", ["-L", _clean(users), "-P", _clean(passwords), t, _clean(service)], timeout=300).text()


# --- recon / post-exploit ------------------------------------------------- #
def theharvester(domain=""):
    if not is_available("theHarvester"):
        return missing_hint("theHarvester")
    d = _clean(domain)
    if not d:
        return "domain required"
    return run("theHarvester", ["-d", d, "-b", "all"], timeout=300).text()


def secretsdump(target=""):
    if not is_available("impacket-secretsdump"):
        return missing_hint("impacket-secretsdump", "python3-impacket")
    t = _clean(target)
    if not t:
        return "target required (e.g. user:pass@10.10.10.5 or -dc-ip ...)"
    args = [a for a in shlex.split(t) if not any(c in a for c in _BAD)]
    return run("impacket-secretsdump", args, timeout=300).text()


# --- generic: run ANY kali tool ------------------------------------------- #
def kali_run(name="", args="", timeout=300):
    """Run any installed Kali tool by name with a space-separated arg string."""
    from .catalog import all_tools
    n = _clean(name)
    if not n or "/" in n or ".." in n:
        return "invalid tool name"
    if not is_available(n) and n not in all_tools():
        return f"tool '{n}' is not a known/installed Kali tool"
    arg_list = [a for a in shlex.split(str(args)) if not any(c in a for c in _BAD)]
    try:
        to = max(10, min(int(timeout), 3600))
    except Exception:
        to = 300
    return run(n, arg_list, timeout=to).text()


def kali_catalog():
    """Return the ShadowDragon Kali tool catalog grouped by category."""
    from .catalog import KALI_CATALOG
    lines = ["ShadowDragon Kali tool catalog (non-networking):"]
    for cat, tools in KALI_CATALOG.items():
        lines.append(f"  {cat}: {', '.join(tools)}")
    lines.append("\nUse kali_run(name, args) to run any of these.")
    return "\n".join(lines)


def kali_installed():
    """Return which catalog tools are actually present on this host."""
    from .catalog import KALI_CATALOG
    present, absent = [], []
    seen = set()
    for tools in KALI_CATALOG.values():
        for t in tools:
            if t in seen:
                continue
            seen.add(t)
            (present if is_available(t) else absent).append(t)
    return (f"installed ({len(present)}): {', '.join(present) or 'none'}\n"
            f"missing ({len(absent)}): {', '.join(absent) or 'none'}")
