"""Secrets backed by the user's native operating-system credential store."""
from __future__ import annotations

import os

SERVICE = "cyberspace"


class CredentialStoreError(RuntimeError):
    """Raised when no secure native credential store is available."""


def _backend():
    try:
        import keyring
        backend = keyring.get_keyring()
        # keyring's fail/null backends deliberately do not store secrets securely.
        if getattr(backend, "priority", 0) <= 0:
            raise CredentialStoreError("no native credential store is available")
        return keyring
    except CredentialStoreError:
        raise
    except Exception as exc:
        raise CredentialStoreError(f"native credential store unavailable: {exc}") from exc


def set_secret(name: str, value: str) -> None:
    """Store or remove a secret in Keychain, Credential Locker, or Secret Service."""
    keyring = _backend()
    try:
        if value:
            keyring.set_password(SERVICE, name, value)
        else:
            try:
                keyring.delete_password(SERVICE, name)
            except keyring.errors.PasswordDeleteError:
                pass
    except Exception as exc:
        raise CredentialStoreError(f"could not save secret in the native credential store: {exc}") from exc


def get_secret(name: str, env_var: str = "") -> str:
    """Read an environment override first, then the native credential store."""
    if env_var and os.environ.get(env_var):
        return os.environ[env_var]
    try:
        return _backend().get_password(SERVICE, name) or ""
    except Exception:
        return ""


def delete_secret(name: str) -> None:
    set_secret(name, "")