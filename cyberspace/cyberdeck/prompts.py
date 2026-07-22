"""Ordered Cyberdeck prompt records.

Every Agent and Swarm user turn is appended before model execution. Records have
a stable sequence number, timestamp, source, project, label, prompt text, response,
and completion state. Labels may be supplied as ``[label: name]`` at the start of
a prompt; otherwise a deterministic label is derived from the prompt text.
"""
from __future__ import annotations

import json
import os
import re
import time
import uuid
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from threading import RLock
from typing import Optional

from ..config import HOME, ensure_dirs

CYBERDECK_DIR = HOME / "cyberdeck"
PROMPTS_FILE = CYBERDECK_DIR / "prompts.jsonl"
LOCK_FILE = CYBERDECK_DIR / ".prompts.lock"
MIGRATION_FILE = CYBERDECK_DIR / ".prompts-migrated"
_LOCK = RLock()

_LABEL_RE = re.compile(r"^\s*\[label\s*:\s*([^\]]+)\]", re.IGNORECASE)
_WORDS_RE = re.compile(r"[a-zA-Z0-9]+")
_STOP_WORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "can", "could", "do",
    "for", "from", "how", "i", "in", "is", "it", "me", "my", "of", "on",
    "please", "the", "this", "to", "use", "want", "what", "with", "would", "you",
}


@contextmanager
def _file_lock(timeout: float = 10.0):
    _private_directory(CYBERDECK_DIR)
    token = f"{os.getpid()}:{uuid.uuid4().hex}"
    deadline = time.monotonic() + timeout
    while True:
        try:
            fd = os.open(LOCK_FILE, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            os.write(fd, (token + "\n").encode())
            os.fsync(fd)
            break
        except FileExistsError:
            try:
                owner = LOCK_FILE.read_text().strip().split(":", 1)[0]
                if owner.isdigit() and not _pid_alive(int(owner)):
                    LOCK_FILE.unlink()
                    continue
            except (OSError, ValueError):
                pass
            if time.monotonic() >= deadline:
                raise TimeoutError("timed out waiting for the Cyberdeck prompt-record lock")
            time.sleep(0.05)
    try:
        yield
    finally:
        os.close(fd)
        try:
            if LOCK_FILE.read_text().strip() == token:
                LOCK_FILE.unlink()
        except OSError:
            pass


def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
        return True
    except PermissionError:
        return True
    except OSError:
        return False


def _private_directory(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    path.chmod(0o700)


def _sanitize_label(value: str) -> str:
    words = _WORDS_RE.findall(value.lower())
    return "-".join(words[:8])[:64] or "prompt"


def explicit_label(prompt: str) -> str:
    """Return a leading ``[label: ...]`` value without changing prompt text."""
    match = _LABEL_RE.match(prompt or "")
    return _sanitize_label(match.group(1)) if match else ""


def automatic_label(prompt: str, sequence: int = 0) -> str:
    """Derive a short, deterministic label from significant prompt words."""
    words = [word.lower() for word in _WORDS_RE.findall(prompt or "")
             if word.lower() not in _STOP_WORDS]
    label = "-".join(words[:6])[:56]
    return label or f"prompt-{sequence:06d}"


def _read_unlocked() -> list[dict]:
    if not PROMPTS_FILE.exists():
        return []
    rows = []
    for line in PROMPTS_FILE.read_text().splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
            if isinstance(row, dict):
                rows.append(row)
        except Exception:
            continue
    return sorted(rows, key=lambda row: int(row.get("sequence", 0)))


def _write_unlocked(rows: list[dict]) -> None:
    ensure_dirs()
    _private_directory(CYBERDECK_DIR)
    tmp = PROMPTS_FILE.with_suffix(f".jsonl.tmp.{os.getpid()}")
    payload = "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows)
    fd = os.open(tmp, os.O_CREAT | os.O_TRUNC | os.O_WRONLY, 0o600)
    with os.fdopen(fd, "w") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
    tmp.chmod(0o600)
    os.replace(tmp, PROMPTS_FILE)
    PROMPTS_FILE.chmod(0o600)
    if hasattr(os, "O_DIRECTORY"):
        dir_fd = os.open(CYBERDECK_DIR, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(dir_fd)
        finally:
            os.close(dir_fd)


def _project() -> str:
    try:
        from ..projects import get_active
        return get_active() or ""
    except Exception:
        return ""


def record_prompt(prompt: str, *, label: str = "", source: str = "agent",
                  project: Optional[str] = None) -> dict:
    """Append a user prompt immediately and return its persisted record."""
    text = str(prompt or "").strip()
    if not text:
        raise ValueError("prompt text is required")
    _migrate_project_prompts()
    with _LOCK, _file_lock():
        rows = _read_unlocked()
        sequence = max((int(row.get("sequence", 0)) for row in rows), default=0) + 1
        supplied = _sanitize_label(label) if label else explicit_label(text)
        record = {
            "sequence": sequence,
            "ts": datetime.now().isoformat(),
            "label": supplied or automatic_label(text, sequence),
            "label_source": "user" if supplied else "automatic",
            "source": _sanitize_label(source),
            "project": _project() if project is None else str(project),
            "prompt": text,
            "response": "",
            "status": "pending",
        }
        rows.append(record)
        _write_unlocked(rows)
        return dict(record)


def complete_prompt(sequence: int, response: str = "", *, status: str = "completed") -> bool:
    """Attach the final response/status without changing record order."""
    with _LOCK, _file_lock():
        rows = _read_unlocked()
        changed = False
        for row in rows:
            if int(row.get("sequence", 0)) == int(sequence):
                row["response"] = str(response or "")
                row["status"] = status
                row["completed_ts"] = datetime.now().isoformat()
                changed = True
                break
        if changed:
            _write_unlocked(rows)
        return changed


def set_label(sequence: int, label: str) -> bool:
    """Replace a record label while preserving its sequence and prompt."""
    _migrate_project_prompts()
    new_label = _sanitize_label(label)
    with _LOCK, _file_lock():
        rows = _read_unlocked()
        changed = False
        for row in rows:
            if int(row.get("sequence", 0)) == int(sequence):
                row["label"] = new_label
                row["label_source"] = "user"
                changed = True
                break
        if changed:
            _write_unlocked(rows)
        return changed


def list_prompts(*, query: str = "", label: str = "", limit: int = 50,
                 project: Optional[str] = None) -> list[dict]:
    """Return records in insertion order, optionally filtered by text or label."""
    _migrate_project_prompts()
    rows = _read_unlocked()
    q = query.lower().strip()
    wanted_label = _sanitize_label(label) if label else ""
    if project is not None:
        rows = [row for row in rows if row.get("project", "") == project]
    if q:
        rows = [row for row in rows if q in (
            f"{row.get('label', '')} {row.get('prompt', '')} {row.get('response', '')}"
        ).lower()]
    if wanted_label:
        rows = [row for row in rows if row.get("label") == wanted_label]
    return rows[-max(1, min(int(limit), 1000)):]


def get_prompt(sequence: int) -> Optional[dict]:
    _migrate_project_prompts()
    for row in _read_unlocked():
        if int(row.get("sequence", 0)) == int(sequence):
            return row
    return None


def _migrate_project_prompts() -> None:
    """Import existing project prompt files once, ordered by their timestamps."""
    if MIGRATION_FILE.exists():
        return
    with _LOCK, _file_lock():
        if MIGRATION_FILE.exists():
            return
        rows = _read_unlocked()
        existing = {(row.get("ts", ""), row.get("prompt", "")) for row in rows}
        candidates = []
        projects_dir = HOME / "projects"
        if projects_dir.exists():
            for prompt_file in projects_dir.glob("*/prompts.jsonl"):
                for line in prompt_file.read_text().splitlines():
                    try:
                        entry = json.loads(line)
                    except Exception:
                        continue
                    prompt = str(entry.get("prompt", "")).strip()
                    ts = str(entry.get("ts", ""))
                    if prompt and (ts, prompt) not in existing:
                        candidates.append((ts, prompt_file.parent.name, entry))
        episodes_file = HOME / "memory" / "episodes.jsonl"
        if episodes_file.exists():
            for line in episodes_file.read_text().splitlines():
                try:
                    episode = json.loads(line)
                except Exception:
                    continue
                if episode.get("action") != "user_objective":
                    continue
                prompt = str((episode.get("args") or {}).get("prompt", "")).strip()
                ts = str(episode.get("ts", ""))
                if prompt and (ts, prompt) not in existing:
                    candidates.append((ts, "", {
                        "ts": ts, "prompt": prompt, "response": "",
                        "source": "swarm-import",
                    }))
        candidates.sort(key=lambda item: item[0])
        candidates = _reconcile_candidates(candidates)
        sequence = max((int(row.get("sequence", 0)) for row in rows), default=0)
        seen_candidates = set(existing)
        for ts, project, entry in candidates:
            sequence += 1
            prompt = str(entry.get("prompt", "")).strip()
            identity = (ts, prompt)
            if identity in seen_candidates:
                sequence -= 1
                continue
            seen_candidates.add(identity)
            supplied = explicit_label(prompt)
            rows.append({
                "sequence": sequence,
                "ts": ts or datetime.now().isoformat(),
                "label": supplied or automatic_label(prompt, sequence),
                "label_source": "user" if supplied else "automatic",
                "source": entry.get("source", "project-import"),
                "project": project,
                "prompt": prompt,
                "response": str(entry.get("response", "")),
                "status": "completed" if entry.get("response") else "recorded",
                "migrated": True,
            })
        _write_unlocked(rows)
        fd = os.open(MIGRATION_FILE, os.O_CREAT | os.O_TRUNC | os.O_WRONLY, 0o600)
        with os.fdopen(fd, "w") as handle:
            handle.write(datetime.now().isoformat())
            handle.flush()
            os.fsync(handle.fileno())


def _parse_ts(value: str) -> Optional[datetime]:
    try:
        return datetime.fromisoformat(value)
    except (TypeError, ValueError):
        return None


def _reconcile_candidates(candidates: list[tuple]) -> list[tuple]:
    """Merge duplicate legacy prompt copies recorded within ten seconds."""
    reconciled: list[tuple] = []
    for candidate in candidates:
        ts, project, entry = candidate
        prompt = str(entry.get("prompt", "")).strip()
        stamp = _parse_ts(ts)
        duplicate_index = None
        for index in range(len(reconciled) - 1, -1, -1):
            old_ts, _old_project, old_entry = reconciled[index]
            if str(old_entry.get("prompt", "")).strip() != prompt:
                continue
            old_stamp = _parse_ts(old_ts)
            if stamp and old_stamp and abs((stamp - old_stamp).total_seconds()) <= 10:
                duplicate_index = index
                break
        if duplicate_index is None:
            reconciled.append(candidate)
            continue
        old = reconciled[duplicate_index]
        # Prefer the project record because it can contain the provider response.
        old_response = str(old[2].get("response", ""))
        new_response = str(entry.get("response", ""))
        if new_response and not old_response:
            reconciled[duplicate_index] = candidate
    return reconciled
