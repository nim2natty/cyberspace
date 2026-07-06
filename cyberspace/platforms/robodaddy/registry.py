"""Model registry + API-key management for RoboDaddy.

Each trained model gets a record (base, dataset, stats, status). When served, it
gets an OpenAI-compatible endpoint + key so it can be plugged back into cyberbot
via `cyberspace iceberg model provider custom --base-url ... --api-key ...`.

Persisted to ~/.cyberspace/modules/robodaddy/.
"""
from __future__ import annotations

import json
import secrets
from dataclasses import dataclass, asdict, field
from datetime import datetime
from pathlib import Path
from threading import RLock
from typing import Optional

from ...config import MODULES_DIR, ensure_dirs

T_DIR = MODULES_DIR / "robodaddy"
MODELS_FILE = T_DIR / "models.json"
KEYS_FILE = T_DIR / "keys.json"
_LOCK = RLock()


@dataclass
class TrainedModel:
    name: str
    base_model: str
    dataset_id: str
    use_case: str
    method: str
    created: str = ""
    status: str = "planned"            # planned | training | trained | served
    stats: dict = field(default_factory=dict)   # loss, samples, hours, cost
    endpoint: Optional[str] = None     # OpenAI-compatible URL when served
    served_model_name: Optional[str] = None


@dataclass
class ApiKey:
    key: str
    model_name: str
    endpoint: str
    created: str
    note: str = ""


def _load(path: Path) -> list:
    ensure_dirs()
    if not path.exists():
        return []
    try:
        return json.loads(path.read_text())
    except Exception:
        return []


def _save(path: Path, data: list) -> None:
    ensure_dirs()
    T_DIR.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2))


def list_models() -> list[TrainedModel]:
    with _LOCK:
        return [TrainedModel(**{k: m[k] for k in TrainedModel.__dataclass_fields__ if k in m})
                for m in _load(MODELS_FILE)]


def get_model(name: str) -> Optional[TrainedModel]:
    with _LOCK:
        for m in list_models():
            if m.name == name:
                return m
    return None


def upsert_model(model: TrainedModel) -> None:
    with _LOCK:
        models = _load(MODELS_FILE)
        models = [m for m in models if m.get("name") != model.name]
        models.append(asdict(model))
        _save(MODELS_FILE, models)


def list_keys() -> list[ApiKey]:
    with _LOCK:
        return [ApiKey(**{k: k2[k] for k in ApiKey.__dataclass_fields__ if k in k2})
                for k2 in _load(KEYS_FILE)]


def issue_key(model_name: str, endpoint: str, note: str = "") -> ApiKey:
    """Generate a new API key for a served model and persist it."""
    with _LOCK:
        key = ApiKey(
            key=f"rbd_" + secrets.token_urlsafe(32),
            model_name=model_name, endpoint=endpoint,
            created=datetime.now().isoformat(), note=note,
        )
        keys = _load(KEYS_FILE)
        keys.append(asdict(key))
        _save(KEYS_FILE, keys)
        # Mark the model served.
        m = get_model(model_name)
        if m:
            m.status = "served"
            m.endpoint = endpoint
            m.served_model_name = model_name
            upsert_model(m)
        return key


def revoke_key(key_prefix: str) -> int:
    with _LOCK:
        keys = _load(KEYS_FILE)
        before = len(keys)
        keys = [k for k in keys if not k["key"].startswith(key_prefix)]
        _save(KEYS_FILE, keys)
        return before - len(keys)
