"""Scrape result pages for Iceberg.

Adapted from Robin's scrape.py (MIT, apurvsinghgautam): fetch each result URL
through Tor (for .onion) or directly (clearnet), pull the visible text with
BeautifulSoup, cap size, and return {url: text}. Thread-safe per-thread sessions.
"""
from __future__ import annotations

import logging
import random
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse

try:
    import requests
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry
except ImportError as exc:  # pragma: no cover
    raise RuntimeError("pip install requests pysocks beautifulsoup4") from exc

from .engines import USER_AGENTS

_log = logging.getLogger(__name__)
MAX_DOWNLOAD_BYTES = 1_000_000
MAX_EXTRACTED_CHARS = 50_000
MAX_RETURN_CHARS = 2_000
ALLOWED_CONTENT_TYPES = ("text/html", "application/xhtml+xml", "text/plain")
_local = threading.local()


def _build_session(use_tor: bool, socks: str) -> "requests.Session":
    s = requests.Session()
    retry = Retry(total=3, read=3, connect=3, backoff_factor=0.3,
                  status_forcelist=[500, 502, 503, 504],
                  allowed_methods=frozenset(["GET", "HEAD"]),
                  respect_retry_after_header=True, raise_on_status=False)
    adapter = HTTPAdapter(max_retries=retry, pool_connections=20, pool_maxsize=20)
    s.mount("http://", adapter)
    s.mount("https://", adapter)
    if use_tor:
        s.proxies = {"http": socks, "https": socks}
    return s


def _get_session(use_tor: bool, socks: str):
    key = "tor" if use_tor else "direct"
    sess = getattr(_local, key, None)
    if sess is None:
        sess = _build_session(use_tor, socks)
        setattr(_local, key, sess)
    return sess


def _norm(item) -> tuple[str, str]:
    if not isinstance(item, dict):
        return "", "Untitled"
    url = str(item.get("link") or "").strip()
    title = str(item.get("title") or "Untitled").strip() or "Untitled"
    return url, title


def scrape_single(url_data: dict, socks: str = "socks5h://127.0.0.1:9050") -> tuple[str, str]:
    """Scrape one {title, link}. Returns (url, 'title - text')."""
    url, title = _norm(url_data)
    if not url:
        return "", title
    if urlparse(url).scheme not in ("http", "https"):
        return url, title
    use_tor = (urlparse(url).hostname or "").lower().endswith(".onion")
    headers = {"User-Agent": random.choice(USER_AGENTS),
               "Accept": "text/html,application/xhtml+xml,text/plain;q=0.9,*/*;q=0.8"}
    resp = None
    try:
        sess = _get_session(use_tor, socks)
        timeout = (10, 45) if use_tor else (5, 25)
        resp = sess.get(url, headers=headers, timeout=timeout, stream=True,
                        verify=not use_tor)
        if resp.status_code != 200:
            return url, title
        ctype = (resp.headers.get("Content-Type") or "").lower()
        if ctype and not any(t in ctype for t in ALLOWED_CONTENT_TYPES):
            return url, title
        chunks, n = [], 0
        for chunk in resp.iter_content(chunk_size=8192):
            if not chunk:
                continue
            n += len(chunk)
            if n > MAX_DOWNLOAD_BYTES:
                break
            chunks.append(chunk)
        html = b"".join(chunks).decode(resp.encoding or "utf-8", errors="replace")
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "html.parser")
        for s in soup(["script", "style"]):
            s.extract()
        text = " ".join(soup.get_text(separator=" ").split())[:MAX_EXTRACTED_CHARS]
        return url, (f"{title} - {text}" if text else title)
    except Exception as e:
        _log.debug("scrape failed %s: %s", url, e)
        return url, title
    finally:
        if resp is not None:
            try:
                resp.close()
            except Exception:
                pass


def scrape_multiple(urls_data: list[dict], socks: str = "socks5h://127.0.0.1:9050",
                    max_workers: int = 5) -> dict[str, str]:
    """Scrape many results concurrently. Returns {url: text}."""
    max_workers = max(1, min(int(max_workers), 16))
    results: dict[str, str] = {}
    seen, uniq = set(), []
    for item in urls_data or []:
        url, title = _norm(item)
        if not url or url in seen:
            continue
        seen.add(url)
        uniq.append({"link": url, "title": title})
    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futs = {ex.submit(scrape_single, d, socks): d for d in uniq}
        for fut in as_completed(futs):
            try:
                url, content = fut.result()
                if not url:
                    continue
                if len(content) > MAX_RETURN_CHARS:
                    content = content[: MAX_RETURN_CHARS - 14] + "...(truncated)"
                results[url] = content
            except Exception as e:
                _log.debug("worker failed: %s", e)
    return results
