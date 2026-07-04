"""AirBender super-tool: expanded networking catalog + chain engine.

Merges ALL networking tools under one CLI with interlinked commands. Each step's
output feeds the next, so the user (or AI) can run pipelines like:
  ping-sweep -> nmap top-ports -> service-detect
in one command. Every tool records to memory for personalization.
"""
from __future__ import annotations

import re
import shlex
from ...host import is_available, missing_hint, run
from .._common import clean_target, clean_value

NETWORKING_TOOLS = [
    "nmap", "masscan", "airmon-ng", "airodump-ng", "aireplay-ng", "aircrack-ng",
    "airbase-ng", "netdiscover", "arp-scan", "traceroute", "whois", "dig",
    "tcpdump", "tshark", "nc", "fping",
]


def _tool_nmap(target="127.0.0.1", args="-sV -T4", timeout=300):
    if not is_available("nmap"): return missing_hint("nmap")
    if clean_target(target): return f"invalid target: {target}"
    safe = [a for a in shlex.split(str(args)) if not clean_target(a)]
    return run("nmap", [*safe, target], timeout=timeout).text()


def _tool_masscan(target="127.0.0.1", ports="1-1000", rate=1000, timeout=300):
    if not is_available("masscan"): return missing_hint("masscan")
    if clean_target(target): return f"invalid target: {target}"
    return run("masscan", ["-p"+str(ports), "--rate", str(int(rate)), target],
               timeout=timeout).text()


def _tool_ping_sweep(target="192.168.1.0/24", timeout=120):
    if not is_available("nmap"): return missing_hint("nmap")
    if clean_target(target): return f"invalid target: {target}"
    return run("nmap", ["-sn", target], timeout=timeout).text()


def _tool_netdiscover(target="192.168.1.0/24", timeout=60):
    if not is_available("netdiscover"): return missing_hint("netdiscover")
    if clean_target(target): return f"invalid target: {target}"
    return run("netdiscover", ["-r", target], timeout=timeout).text()


def _tool_arp_scan(timeout=60):
    if not is_available("arp-scan"): return missing_hint("arp-scan")
    return run("arp-scan", ["--localnet"], timeout=timeout).text()


def _tool_traceroute(target="8.8.8.8", timeout=60):
    if not is_available("traceroute"): return missing_hint("traceroute")
    if clean_target(target): return f"invalid target: {target}"
    return run("traceroute", [target], timeout=timeout).text()


def _tool_whois(domain="example.com", timeout=30):
    if not is_available("whois"): return missing_hint("whois")
    d = clean_value(domain)
    if not d: return "domain required"
    return run("whois", [d], timeout=timeout).text()


def _tool_dig(domain="example.com", rtype="A", server="", timeout=20):
    if not is_available("dig"): return missing_hint("dig")
    d = clean_value(domain)
    if not d: return "domain required"
    args = [d, str(rtype)]
    if server: args = ["@"+clean_value(server)] + args
    return run("dig", args, timeout=timeout).text()


def _tool_tcpdump(interface="eth0", count=10, filter_expr="", timeout=30):
    if not is_available("tcpdump"): return missing_hint("tcpdump")
    args = ["-i", clean_value(interface), "-c", str(int(count)), "-n"]
    if filter_expr: args += [clean_value(filter_expr)]
    return run("tcpdump", args, timeout=timeout).text()


def _tool_airmon(iface="wlan0", action="start", timeout=10):
    if not is_available("airmon-ng"): return missing_hint("airmon-ng")
    return run("airmon-ng", [clean_value(action), clean_value(iface)], timeout=timeout).text()


def _tool_airodump(iface="wlan0mon", channel="", bssid="", timeout=20):
    if not is_available("airodump-ng"): return missing_hint("airodump-ng")
    args = ["-i", clean_value(iface)]
    if channel: args += ["-c", str(int(channel))]
    if bssid: args += ["--bssid", clean_value(bssid)]
    return run("airodump-ng", args, timeout=timeout).text()


def _tool_netcat(target="127.0.0.1", port=80, mode="scan", timeout=10):
    if not is_available("nc"): return missing_hint("netcat")
    p = int(port)
    if mode == "scan":
        return run("nc", ["-zv", "-w3", clean_value(target), str(p)], timeout=timeout).text()
    return run("nc", [clean_value(target), str(p)], timeout=timeout).text()


# --- output parsers (extract data to feed the next step) ------------------ #
def _parse_hosts(text: str) -> list[str]:
    """Extract IP addresses from nmap/ping-sweep/netdiscover output."""
    return list(dict.fromkeys(re.findall(r'\b(?:\d{1,3}\.){3}\d{1,3}\b', text or "")))


# --- named pipeline steps -------------------------------------------------- #
CHAIN_STEPS = {
    "ping-sweep": {"desc": "discover live hosts on a subnet",
                   "fn": lambda t, **k: _tool_ping_sweep(target=t),
                   "parse": _parse_hosts, "output": "hosts"},
    "nmap-top": {"desc": "scan top 1000 ports on hosts",
                 "fn": lambda t, **k: _tool_nmap(target=t, args="--top-ports 1000 -T4", timeout=600),
                 "output": "raw"},
    "service-detect": {"desc": "service/version detection",
                       "fn": lambda t, **k: _tool_nmap(target=t, args="-sV -T4", timeout=600),
                       "output": "raw"},
    "masscan-fast": {"desc": "fast masscan all ports on targets",
                     "fn": lambda t, **k: _tool_masscan(target=t, ports="1-65535", rate=10000, timeout=600),
                     "output": "raw"},
    "web-detect": {"desc": "identify web services (http ports)",
                   "fn": lambda t, **k: _tool_nmap(target=t,
                       args="-p 80,443,8080,8443 -sV --script http-title", timeout=300),
                   "output": "raw"},
}


def run_chain(steps: list[str], target: str, on_event=None) -> dict:
    """Execute a pipeline of named steps, feeding outputs forward."""
    on_event = on_event or (lambda s, m: None)
    from ...memory import record
    results = {}
    current = target

    for step_name in steps:
        step = CHAIN_STEPS.get(step_name)
        if not step:
            msg = f"unknown step '{step_name}'. Available: {', '.join(CHAIN_STEPS)}"
            on_event("error", msg); results[step_name] = msg; break
        on_event(step_name, f"running {step_name} on {current}...")
        try:
            raw = step["fn"](current)
        except Exception as e:
            raw = f"ERROR: {e}"
        results[step_name] = raw[:2000]
        record("airbender", step_name, {"target": current}, raw[:300])
        on_event(step_name, f"done ({len(raw)} chars)")
        if step["output"] == "hosts" and step.get("parse"):
            hosts = step["parse"](raw)
            if hosts:
                current = " ".join(hosts[:50])
                on_event(step_name, f"found {len(hosts)} hosts -> next step")
            else:
                on_event(step_name, "no hosts found - chain stops"); break
    return results


# Predefined pipelines (user-friendly shortcuts).
PIPELINES = {
    "recon": {"desc": "full recon: discover hosts -> scan ports -> detect services",
              "steps": ["ping-sweep", "nmap-top", "service-detect"]},
    "fast-scan": {"desc": "quick: discover hosts -> masscan all ports",
                  "steps": ["ping-sweep", "masscan-fast"]},
    "web-hunt": {"desc": "find web apps: discover hosts -> detect web ports",
                 "steps": ["ping-sweep", "web-detect"]},
}
