"""Refresh and cache the most recent Hugging Face datasets for RoboDaddy.

The guided ``start`` flow runs :func:`refresh_datasets_cache` so the user can
view the latest datasets in their local database (``latest_datasets``) without
re-hitting the network every time. The cache is plain JSON on disk.
"""
from __future__ import annotations

import json
from datetime import datetime
from typing import Optional

from ...config import MODULES_DIR, ensure_dirs

CACHE_FILE = MODULES_DIR / "robodaddy" / "latest_datasets.json"


def refresh_datasets_cache(limit_per_term: int = 15, *, client=None,
                           search_terms: Optional[list[str]] = None,
                           on_event=None) -> list[dict]:
    """Search the most recent Hugging Face datasets and cache them locally.

    Returns the freshly cached dataset list (most recent first). Safe to call
    offline: on any failure it falls back to the curated catalog.
    """
    from .discovery import discover_recent_datasets
    ensure_dirs()
    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    if on_event:
        on_event("search", "searching most recent Hugging Face datasets...")
    datasets = discover_recent_datasets(limit=limit_per_term, client=client,
                                        search_terms=search_terms)
    payload = {
        "refreshed": datetime.now().isoformat(),
        "count": len(datasets),
        "datasets": datasets,
    }
    CACHE_FILE.write_text(json.dumps(payload, indent=2))
    if on_event:
        on_event("done", f"cached {len(datasets)} latest datasets -> {CACHE_FILE}")
    return datasets


def latest_datasets(limit: int = 0) -> list[dict]:
    """Return the locally cached latest datasets (empty if not refreshed yet)."""
    if not CACHE_FILE.exists():
        return []
    try:
        data = json.loads(CACHE_FILE.read_text())
        datasets = data.get("datasets", []) if isinstance(data, dict) else []
        return datasets[:limit] if limit and limit > 0 else datasets
    except Exception:
        return []


def cache_info() -> dict:
    """Return cache metadata (refreshed time + count), or empty dict."""
    if not CACHE_FILE.exists():
        return {}
    try:
        data = json.loads(CACHE_FILE.read_text())
        return {"refreshed": data.get("refreshed", ""), "count": data.get("count", 0)}
    except Exception:
        return {}
