"""Search the IceBerg :: e engines (brightside clearnet or darkside onion).

Adapted from Robin's search.py (MIT, apurvsinghgautam): build the query URL for
each engine, fetch via the right transport (direct for bright, Tor SOCKS5h for
dark), parse anchors, and extract result links. Onion mode harvests *.onion
links; bright mode harvests normal http(s) links.
"""
from __future__ import annotations

import random
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional
from urllib.parse import urlparse

from .engines import USER_AGENTS, engines_for

# requests is a core dependency of this module; pysocks enables socks5h:// for Tor.
try:
    import requests
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry
except ImportError as exc:  # pragma: no cover - import guard
    requests = None
    raise RuntimeError(
        "The 'e' tool needs 'requests' + 'pysocks'. Install with: "
        "pip install requests pysocks beautifulsoup4"
    ) from exc


def _session_for(use_tor: bool, socks_url: str) -> "requests.Session":
    s = requests.Session()
    retry = Retry(total=3, read=3, connect=3, backoff_factor=0.5,
                  status_forcelist=[500, 502, 503, 504])
    s.mount("http://", HTTPAdapter(max_retries=retry))
    s.mount("https://", HTTPAdapter(max_retries=retry))
    if use_tor:
        # socks5h => Tor resolves DNS (mandatory for .onion hostnames).
        s.proxies = {"http": socks_url, "https": socks_url}
    return s


def _is_onion(url: str) -> bool:
    try:
        return (urlparse(url).hostname or "").lower().endswith(".onion")
    except Exception:
        return False


def fetch_engine(engine: dict, query: str, *, use_tor: bool, socks: str,
                 timeout: int = 40) -> list[dict]:
    """Query one engine and return [{title, link}, ...]."""
    url = engine["url"].format(query=query)
    try:
        session = _session_for(use_tor, socks)
        resp = session.get(url, headers={"User-Agent": random.choice(USER_AGENTS)},
                           timeout=timeout, verify=not use_tor)
    except Exception:
        return []
    if resp.status_code != 200:
        return []
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        return []
    soup = BeautifulSoup(resp.text, "html.parser")
    out: list[dict] = []
    want_onion = use_tor
    for a in soup.find_all("a"):
        try:
            href = a.get("href", "") or ""
            title = a.get_text(strip=True)
            if want_onion:
                m = re.findall(r"https?://[a-z0-9.]+\.onion[^\s\"'<>]*", href)
                if m and "search" not in m[0] and len(title) > 3:
                    out.append({"title": title[:200], "link": m[0]})
            else:
                # Bright mode: resolve relative links and take http(s).
                absu = href if href.startswith("http") else ""
                if absu and not _is_onion(absu):
                    host = urlparse(absu).hostname or ""
                    if host and "search" not in absu and len(title) > 3:
                        out.append({"title": title[:200], "link": absu})
        except Exception:
            continue
    return out


def get_search_results(query: str, mode: str = "dark", *, socks: str = "socks5h://127.0.0.1:9050",
                       max_workers: int = 5) -> list[dict]:
    """Query every engine for the mode in parallel, dedupe, and return results.

    mode: 'bright' (clearnet, direct) or 'dark' (onion, via Tor SOCKS5h).
    """
    use_tor = (mode == "dark")
    engines = engines_for(mode)
    results: list[dict] = []
    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futures = [ex.submit(fetch_engine, eng, query, use_tor=use_tor, socks=socks)
                   for eng in engines]
        for fut in as_completed(futures):
            results.extend(fut.result())
    # Dedupe by normalized link.
    seen, unique = set(), []
    for r in results:
        key = (r.get("link", "") or "").rstrip("/")
        if key and key not in seen:
            seen.add(key)
            unique.append(r)
    return unique
