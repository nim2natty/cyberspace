"""Shared utilities for platform modules."""
from __future__ import annotations

_BAD = (";", "|", "&", "`", "$", "(", ")", "\n", "\r", ">", "<")


def clean_target(target: str) -> str | None:
    """Validate target (CIDR/IP/hostname). Returns error string or None if OK."""
    target = (target or "").strip()
    if not target or any(c in target for c in (" ", ";", "|", "&", "`", "$", "(", ")")):
        return "invalid target"
    return None


def clean_value(value) -> str:
    """Strip shell metacharacters from a value."""
    if value is None:
        return ""
    return "".join(c for c in str(value) if c not in _BAD).strip()
