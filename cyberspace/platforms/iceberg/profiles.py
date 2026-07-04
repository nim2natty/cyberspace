"""IceBerg fingerprint profiles (ported & condensed from the veil project).

A profile is a complete synthetic identity controlling every value a website
reads to build a fingerprint, plus the network layer (proxy + DoH provider).
"""
from __future__ import annotations

import secrets
from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, Field

from ...config import MODULES_DIR, ensure_dirs  # iceberg uses cyberspace home
from .personas import PERSONAS

PROFILES_DIR = MODULES_DIR / "iceberg" / "profiles"


class FingerprintProfile(BaseModel):
    name: str
    created: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    user_agent: str
    platform: str
    platform_version: str = "0.0.0"
    architecture: str = ""
    bitness: str = "64"
    sec_ch_ua_mobile: str = "?0"
    sec_ch_ua_platform: str = '"Unknown"'
    sec_ch_ua: Optional[str] = None
    ua_full_version_list: Optional[str] = None
    hardware_concurrency: int = 8
    device_memory: int = 8
    max_touch_points: int = 0
    screen_width: int = 1920
    screen_height: int = 1080
    color_depth: int = 24
    device_pixel_ratio: float = 1.0
    timezone: str = "America/New_York"
    locale: str = "en-US"
    languages: list[str] = ["en-US", "en"]
    webgl_vendor: str = "Google Inc. (Intel)"
    webgl_renderer: str = "ANGLE (Intel)"
    fonts: list[str] = ["Arial", "Courier New", "Georgia"]
    proxy: Optional[str] = None
    doh_provider: str = "mullvad"
    noise_seed: str = Field(default_factory=lambda: secrets.token_hex(16))
    webrtc_mode: str = "proxy_only"
    block_tracking: bool = True
    canvas_noise: bool = True
    audio_noise: bool = True

    @classmethod
    def from_persona(cls, name: str, persona: str, **ov) -> "FingerprintProfile":
        if persona not in PERSONAS:
            raise ValueError(f"unknown persona '{persona}'")
        return cls(name=name, **{**PERSONAS[persona], **ov})

    def save(self) -> None:
        PROFILES_DIR.mkdir(parents=True, exist_ok=True)
        (PROFILES_DIR / f"{self.name}.json").write_text(self.model_dump_json(indent=2))

    @classmethod
    def load(cls, name: str) -> "FingerprintProfile":
        p = PROFILES_DIR / f"{name}.json"
        if not p.exists():
            raise FileNotFoundError(f"no IceBerg profile named '{name}'")
        return cls.model_validate_json(p.read_text())

    @classmethod
    def list_names(cls) -> list[str]:
        return sorted(p.stem for p in PROFILES_DIR.glob("*.json")) if PROFILES_DIR.exists() else []

    @classmethod
    def delete(cls, name: str) -> bool:
        p = PROFILES_DIR / f"{name}.json"
        if p.exists():
            p.unlink()
            return True
        return False
