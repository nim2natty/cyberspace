"""Security configuration for the IceBerg :: secure tool.

Darkside (Tor) browsing demands a different OPSEC posture than brightside
(clearnet). This module stores the user's per-mode security settings and applies
Tor-specific hardening (new identity per session, DoH, WebRTC lockdown).

Persisted to ~/.cyberspace/modules/iceberg/e/security.json so the wizard only
needs to run once.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Optional

from ....config import MODULES_DIR, ensure_dirs

E_DIR = MODULES_DIR / "iceberg" / "e"
SECURITY_FILE = E_DIR / "security.json"


@dataclass
class SecurityConfig:
    # Transport
    mode: str = "bright"                       # 'bright' | 'dark'
    tor_socks_host: str = "127.0.0.1"
    tor_socks_port: int = 9050
    tor_control_host: str = "127.0.0.1"
    tor_control_port: int = 9051
    tor_control_password: str = ""
    # Hardening (mostly dark mode)
    new_identity_per_session: bool = True      # NEWNYM before each investigation
    block_webrtc: bool = True                  # never leak LAN/exit IP via ICE
    force_doh: bool = True                     # DNS-over-HTTPS, no plaintext DNS
    doh_provider: str = "mullvad"
    rotate_user_agent: bool = True
    verify_tls: bool = False                   # onion certs are often self-signed
    # Throughput / safety caps
    max_engines: int = 16
    max_results: int = 25
    max_scrape: int = 8
    scrape_timeout: int = 45
    # Brightside-only: an IceBerg fingerprint profile name to reuse for browsing.
    bright_profile: Optional[str] = None
    tags: list[str] = field(default_factory=list)

    def socks_url(self) -> str:
        return f"socks5h://{self.tor_socks_host}:{self.tor_socks_port}"

    @classmethod
    def load(cls) -> "SecurityConfig":
        ensure_dirs()
        if not SECURITY_FILE.exists():
            return cls()
        try:
            d = json.loads(SECURITY_FILE.read_text())
            return cls(**{k: d[k] for k in cls.__dataclass_fields__ if k in d})
        except Exception:
            return cls()

    def save(self) -> None:
        E_DIR.mkdir(parents=True, exist_ok=True)
        SECURITY_FILE.write_text(json.dumps(asdict(self), indent=2))


# Friendly presets the wizard offers, so a learner doesn't face raw fields.
PRESETS = {
    "bright": {
        "label": "Brightside (clearnet, no Tor)",
        "config": SecurityConfig(mode="bright", force_doh=True, block_webrtc=True,
                                 rotate_user_agent=True, verify_tls=True,
                                 max_results=25, max_scrape=8),
    },
    "dark_safe": {
        "label": "Darkside - safe (Tor + full hardening)",
        "config": SecurityConfig(mode="dark", new_identity_per_session=True,
                                 block_webrtc=True, force_doh=True,
                                 doh_provider="mullvad", rotate_user_agent=True,
                                 verify_tls=False, max_results=25, max_scrape=8),
    },
    "dark_fast": {
        "label": "Darkside - fast (Tor, fewer sources)",
        "config": SecurityConfig(mode="dark", new_identity_per_session=True,
                                 block_webrtc=True, force_doh=True,
                                 rotate_user_agent=True, verify_tls=False,
                                 max_engines=6, max_results=15, max_scrape=5),
    },
}


def dark_settings(cfg: SecurityConfig) -> list[str]:
    """Human-readable list of the Tor-specific settings that differ from bright."""
    return [
        f"transport: Tor SOCKS5h @ {cfg.tor_socks_host}:{cfg.tor_socks_port}",
        f"new identity per session: {'yes (NEWNYM)' if cfg.new_identity_per_session else 'no'}",
        f"DNS: {'DoH (' + cfg.doh_provider + ')' if cfg.force_doh else 'system (leaks!)'}",
        f"WebRTC: {'blocked (no IP leak)' if cfg.block_webrtc else 'allowed (leaks!)'}",
        f"TLS verify: {'on' if cfg.verify_tls else 'off (onion self-signed)'}",
        f"sources cap: engines<={cfg.max_engines}, results<={cfg.max_results}, scrape<={cfg.max_scrape}",
    ]
