"""ShadowDragon chain engine: pipelines over registered assessment tools.

Lets the user (or AI) run attack pipelines where each tool's output feeds the
next. Example: whatweb -> searchsploit -> msfconsole. Every step records to memory.
"""
from __future__ import annotations

import re
from . import tools as T


def _parse_urls(text: str) -> list[str]:
    """Extract URLs from whatweb/gobuster/scan output."""
    return list(dict.fromkeys(re.findall(r'https?://[^\s<>"\']+', text or "")))


def _parse_exploits(text: str) -> list[str]:
    """Extract exploit paths from searchsploit output."""
    return re.findall(r'(exploit/[^\s|]+)', text or "")


def _parse_subdomains(text: str) -> list[str]:
    """Extract subdomains from sublist3r/theharvester output."""
    return list(dict.fromkeys(re.findall(r'\b[a-z0-9.-]+\.[a-z]{2,}\b', (text or "").lower())))


# Named pipeline steps. Each fn takes (input_str, **kwargs) and returns text.
CHAIN_STEPS = {
    "whatweb": {"desc": "identify web tech", "fn": lambda t, **k: T.whatweb(url=t),
                "parse": lambda x: x, "output": "raw"},
    "wpscan": {"desc": "WordPress scan", "fn": lambda t, **k: T.wpscan(url=t),
               "output": "raw"},
    "sqlmap": {"desc": "SQL injection test", "fn": lambda t, **k: T.sqlmap(url=t),
               "output": "raw"},
    "gobuster": {"desc": "directory brute force", "fn": lambda t, **k: T.gobuster(url=t),
                 "output": "raw"},
    "nikto": {"desc": "web vuln scan", "fn": lambda t, **k: T.nikto(url=t),
              "output": "raw"},
    "nuclei": {"desc": "template-based vuln scan", "fn": lambda t, **k: T.nuclei(url=t),
               "output": "raw"},
    "searchsploit": {"desc": "search exploitdb for the target/service",
                     "fn": lambda t, **k: T.searchsploit(query=t),
                     "parse": _parse_exploits, "output": "exploits"},
    "theharvester": {"desc": "email/subdomain harvesting",
                     "fn": lambda t, **k: T.theharvester(domain=t),
                     "parse": _parse_subdomains, "output": "hosts"},
    "sublist3r": {"desc": "subdomain enumeration",
                  "fn": lambda t, **k: T.sublist3r(domain=t),
                  "parse": _parse_subdomains, "output": "hosts"},
    "metasploit": {"desc": "run a metasploit exploit module",
                   "fn": lambda t, **k: _msf_step(t, k.get("options", "")),
                   "output": "raw"},
    "john": {"desc": "crack hashes with john",
             "fn": lambda t, **k: T.john(hashfile=t), "output": "raw"},
    "hydra": {"desc": "brute force login with hydra",
              "fn": lambda t, **k: T.hydra(target=t), "output": "raw"},
}


def _msf_step(exploit_str: str, options: str = "") -> str:
    """Run a metasploit module via resource script."""
    from .metasploit import run_exploit
    return run_exploit(exploit_str, options)


def run_chain(steps: list[str], target: str, on_event=None, **step_kwargs) -> dict:
    """Execute an interlinked attack pipeline.

    steps: ["whatweb", "searchsploit", "metasploit"]
    target: the initial target (URL/domain/host)
    Returns {step_name: result_text}
    """
    on_event = on_event or (lambda s, m: None)
    from ...memory import record
    results = {}
    current = target

    for step_name in steps:
        step = CHAIN_STEPS.get(step_name)
        if not step:
            msg = f"unknown step '{step_name}'. Available: {', '.join(CHAIN_STEPS)}"
            on_event("error", msg); results[step_name] = msg; break
        on_event(step_name, f"running {step_name} on {current[:80]}...")
        try:
            raw = step["fn"](current, **step_kwargs)
        except Exception as e:
            raw = f"ERROR: {e}"
        results[step_name] = raw[:3000]
        record("shadowdragon", step_name, {"target": current}, raw[:300])
        on_event(step_name, f"done ({len(raw)} chars)")
        # Transform output for the next step.
        if step["output"] == "exploits" and step.get("parse"):
            exploits = step["parse"](raw)
            if exploits:
                current = exploits[0]
                on_event(step_name, f"found {len(exploits)} exploits -> next: {current}")
            else:
                on_event(step_name, "no exploits found - chain continues with raw")
        elif step["output"] == "hosts" and step.get("parse"):
            hosts = step["parse"](raw)
            if hosts:
                current = hosts[0]
                on_event(step_name, f"found {len(hosts)} items -> next: {current}")
    return results


# Predefined attack pipelines (user-friendly shortcuts).
PIPELINES = {
    "web-recon": {
        "desc": "web recon: whatweb -> nuclei -> searchsploit",
        "steps": ["whatweb", "nuclei", "searchsploit"]},
    "wp-assault": {
        "desc": "WordPress attack: wpscan -> searchsploit -> metasploit",
        "steps": ["wpscan", "searchsploit", "metasploit"]},
    "sqli-exploit": {
        "desc": "SQL injection: sqlmap -> searchsploit",
        "steps": ["sqlmap", "searchsploit"]},
    "subdomain-hunt": {
        "desc": "subdomain recon: sublist3r -> theharvester -> whatweb",
        "steps": ["sublist3r", "theharvester", "whatweb"]},
    "full-assault": {
        "desc": "full web assault: whatweb -> gobuster -> nikto -> searchsploit -> metasploit",
        "steps": ["whatweb", "gobuster", "nikto", "searchsploit", "metasploit"]},
}
