"""End-to-end AI find pipeline for IceBerg :: e.

run_find() wires the whole thing together with a progress callback so both the
CLI and the Streamlit GUI can show each stage:

    query -> refine(LLM) -> search(engines) -> filter(LLM)
          -> scrape(pages) -> summarize(LLM) -> investigation
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable, Optional

from ....config import MODULES_DIR, ensure_dirs
from . import intel
from .scrape import scrape_multiple
from .search import get_search_results
from .security import SecurityConfig
from .tor import new_identity, tor_available

INVESTIGATIONS_DIR = MODULES_DIR / "iceberg" / "e" / "investigations"

EventFn = Callable[[str, str], None]


def _noop(_stage: str, _msg: str) -> None:
    pass


@dataclass
class Investigation:
    query: str
    refined: str = ""
    mode: str = "bright"
    preset: str = "general"
    model: str = ""
    results: list[dict] = field(default_factory=list)
    filtered: list[dict] = field(default_factory=list)
    scraped: dict[str, str] = field(default_factory=dict)
    summary: str = ""
    saved_path: Optional[str] = None


def _ensure_tor_ready(sec: SecurityConfig, on_event: EventFn) -> Optional[str]:
    """Validate Tor for dark mode + request a fresh identity. Returns err or None."""
    if sec.mode != "dark":
        return None
    if not tor_available(sec.tor_socks_host, sec.tor_socks_port):
        msg = (f"Tor SOCKS proxy not reachable at {sec.tor_socks_host}:"
               f"{sec.tor_socks_port}. Start it: 'service tor start' "
               f"/ 'brew services start tor'.")
        on_event("tor", msg)
        return msg
    on_event("tor", f"Tor proxy OK ({sec.socks_url()}).")
    if sec.new_identity_per_session:
        ok, info = new_identity(sec.tor_control_host, sec.tor_control_port,
                                sec.tor_control_password or None)
        on_event("tor", f"{'fresh circuit' if ok else 'no new identity'}: {info}")
    return None


def run_find(query: str, sec: Optional[SecurityConfig] = None,
             preset: str = "general", custom: str = "",
             on_event: Optional[EventFn] = None) -> Investigation:
    """Run the full AI find pipeline. Returns a populated Investigation."""
    on_event = on_event or _noop
    sec = sec or SecurityConfig.load()
    inv = Investigation(query=query, mode=sec.mode, preset=preset)

    err = _ensure_tor_ready(sec, on_event)
    if err:
        inv.summary = f"[blocked] {err}"
        return inv

    on_event("refine", "refining query with the cyberbot LLM...")
    try:
        inv.refined = intel.refine_query(query)
    except Exception as e:
        inv.refined = query
        on_event("refine", f"refine failed ({e}); using raw query")
    on_event("refine", f"refined query: {inv.refined}")

    on_event("search", f"querying {sec.mode} engines via "
             f"{'Tor' if sec.mode == 'dark' else 'direct'}...")
    try:
        inv.results = get_search_results(
            inv.refined.replace(" ", "+"), mode=sec.mode, socks=sec.socks_url())
    except Exception as e:
        on_event("search", f"search error: {e}")
        inv.results = []
    inv.results = inv.results[: sec.max_results]
    on_event("search", f"{len(inv.results)} unique results")
    if not inv.results:
        inv.summary = f"No results found for '{inv.refined}' on the {sec.mode} engines."
        return inv

    on_event("filter", "filtering results for relevance...")
    try:
        inv.filtered = intel.filter_results(inv.refined, inv.results)[: sec.max_scrape]
    except Exception:
        inv.filtered = inv.results[: sec.max_scrape]
    if not inv.filtered:
        inv.filtered = inv.results[: sec.max_scrape]
    on_event("filter", f"{len(inv.filtered)} results kept after filtering")

    on_event("scrape", f"scraping {len(inv.filtered)} pages...")
    try:
        inv.scraped = scrape_multiple(inv.filtered, socks=sec.socks_url())
    except Exception as e:
        on_event("scrape", f"scrape error: {e}")
        inv.scraped = {}
    on_event("scrape", f"scraped {len(inv.scraped)} pages")

    on_event("summary", "generating investigation summary...")
    try:
        inv.summary = intel.generate_summary(inv.refined, inv.scraped,
                                             preset=preset, custom=custom)
    except Exception as e:
        inv.summary = f"[summary failed: {e}]\n\nRaw sources:\n" + "\n".join(
            r.get("link", "") for r in inv.filtered)
    on_event("summary", "done")
    return inv


def save_investigation(inv: Investigation) -> str:
    """Persist an investigation to JSON. Returns the file path."""
    ensure_dirs()
    INVESTIGATIONS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = INVESTIGATIONS_DIR / f"investigation_{ts}.json"
    path.write_text(json.dumps({
        "timestamp": datetime.now().isoformat(), "query": inv.query,
        "refined_query": inv.refined, "mode": inv.mode, "preset": inv.preset,
        "model": inv.model, "filtered_sources": inv.filtered,
        "summary": inv.summary,
    }, indent=2))
    inv.saved_path = str(path)
    return inv.saved_path


def list_investigations() -> list[dict]:
    """Return saved investigations, newest first."""
    if not INVESTIGATIONS_DIR.exists():
        return []
    out = []
    for f in sorted(INVESTIGATIONS_DIR.glob("investigation_*.json"), reverse=True):
        try:
            d = json.loads(f.read_text())
            d["_file"] = f.name
            out.append(d)
        except Exception:
            continue
    return out

