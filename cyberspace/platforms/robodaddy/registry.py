"""Model registry + API-key management for RoboDaddy.

Each trained model gets a record (base, dataset, stats, status). When served, it
gets an OpenAI-compatible endpoint + key so it can be plugged back into cyberbot
via `cyberspace iceberg model provider custom --base-url ... --api-key ...`.

Persisted to ~/.cyberspace/modules/robodaddy/.
"""
from __future__ import annotations

import json
import os
import secrets
import time
from contextlib import contextmanager
from dataclasses import dataclass, asdict, field
from datetime import datetime
from pathlib import Path
from threading import RLock
from typing import Optional

from ...config import MODULES_DIR, ensure_dirs

T_DIR = MODULES_DIR / "robodaddy"
MODELS_FILE = T_DIR / "models.json"
KEYS_FILE = T_DIR / "keys.json"
LOCK_FILE = T_DIR / ".registry.lock"
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
    key_id: str
    prefix: str
    model_name: str
    endpoint: str
    created: str
    note: str = ""

    @property
    def key(self) -> str:
        """Resolve the secret from the native credential store on demand."""
        from ...credentials import get_secret
        return get_secret(f"robodaddy:key:{self.key_id}")


@contextmanager
def _file_lock(timeout: float = 10.0):
    """Small cross-process lock for registry read/modify/write operations."""
    T_DIR.mkdir(parents=True, exist_ok=True)
    deadline = time.monotonic() + timeout
    while True:
        try:
            fd = os.open(LOCK_FILE, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            os.write(fd, f"{os.getpid()}\n".encode())
            break
        except FileExistsError:
            try:
                if time.time() - LOCK_FILE.stat().st_mtime > 300:
                    LOCK_FILE.unlink()
                    continue
            except OSError:
                pass
            if time.monotonic() >= deadline:
                raise TimeoutError("timed out waiting for RoboDaddy registry lock")
            time.sleep(0.05)
    try:
        yield
    finally:
        os.close(fd)
        try:
            LOCK_FILE.unlink()
        except OSError:
            pass


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
    tmp = path.with_suffix(path.suffix + f".tmp.{os.getpid()}")
    tmp.write_text(json.dumps(data, indent=2))
    try:
        tmp.chmod(0o600)
    except OSError:
        pass
    os.replace(tmp, path)


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
        with _file_lock():
            models = _load(MODELS_FILE)
            models = [m for m in models if m.get("name") != model.name]
            models.append(asdict(model))
            _save(MODELS_FILE, models)


def list_keys() -> list[ApiKey]:
    with _LOCK:
        raw = _load(KEYS_FILE)
        migrated = False
        records = []
        from ...credentials import set_secret
        for item in raw:
            if item.get("key") and not item.get("key_id"):
                secret = item.pop("key")
                item["key_id"] = secrets.token_hex(12)
                item["prefix"] = secret[:12]
                set_secret(f"robodaddy:key:{item['key_id']}", secret)
                migrated = True
            try:
                records.append(ApiKey(**{k: item[k] for k in ApiKey.__dataclass_fields__ if k in item}))
            except TypeError:
                continue
        if migrated:
            with _file_lock():
                _save(KEYS_FILE, [asdict(record) for record in records])
        return records


def issue_key(model_name: str, endpoint: str, note: str = "") -> ApiKey:
    """Generate a new API key for a served model and persist it."""
    with _LOCK:
        from ...credentials import set_secret
        secret = f"rbd_" + secrets.token_urlsafe(32)
        key_id = secrets.token_hex(12)
        key = ApiKey(
            key_id=key_id, prefix=secret[:12],
            model_name=model_name, endpoint=endpoint,
            created=datetime.now().isoformat(), note=note,
        )
        set_secret(f"robodaddy:key:{key_id}", secret)
        with _file_lock():
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
        from ...credentials import delete_secret
        with _file_lock():
            keys = _load(KEYS_FILE)
            removed = [k for k in keys if k.get("prefix", "").startswith(key_prefix)
                       or k.get("key_id", "").startswith(key_prefix)]
            kept = [k for k in keys if k not in removed]
            _save(KEYS_FILE, kept)
        for item in removed:
            delete_secret(f"robodaddy:key:{item['key_id']}")
        return len(removed)
