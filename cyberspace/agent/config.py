"""Non-secret agent settings plus native credential-store persistence."""
from __future__ import annotations

import os

from ..config import AGENT_FILE, ensure_dirs
from ..credentials import CredentialStoreError, get_secret, set_secret
from .llm import LLMConfig


def _credential_name(provider: str) -> str:
    return f"llm:{provider or 'custom'}"


def _provider_env(provider: str) -> str:
    try:
        from .providers import get_spec
        spec = get_spec(provider)
        return spec.env_key if spec else ""
    except Exception:
        return ""


def load_config() -> LLMConfig | None:
    if not AGENT_FILE.exists():
        return None
    try:
        data = __import__("json").loads(AGENT_FILE.read_text())
        cfg = LLMConfig.from_dict(data)
        # Migrate legacy plaintext keys once, then immediately rewrite the file.
        legacy_key = data.get("api_key", "")
        if legacy_key:
            try:
                set_secret(_credential_name(cfg.provider), legacy_key)
                save_config(LLMConfig(**{**cfg.__dict__, "api_key": ""}))
            except CredentialStoreError:
                # Never delete the only copy when a headless Linux keyring is absent.
                cfg.api_key = legacy_key
                return cfg
        cfg.api_key = get_secret(_credential_name(cfg.provider), _provider_env(cfg.provider))
        return cfg
    except Exception:
        return None


def save_config(cfg: LLMConfig) -> str:
    """Save settings without secrets; return a description of key storage."""
    ensure_dirs()
    import json
    storage = "not needed"
    if cfg.api_key:
        env_var = _provider_env(cfg.provider)
        if env_var and os.environ.get(env_var) == cfg.api_key:
            storage = f"environment variable ${env_var}"
        else:
            set_secret(_credential_name(cfg.provider), cfg.api_key)
            storage = "native credential store"
    data = {**cfg.__dict__, "api_key": ""}
    AGENT_FILE.write_text(json.dumps(data, indent=2))
    try:
        AGENT_FILE.chmod(0o600)
    except OSError:
        pass
    return storage


def is_configured() -> bool:
    return load_config() is not None
