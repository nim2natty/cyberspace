"""The playbook: learned strategies the Brain feeds forward.

Every operation records an entry: the intent, the plan (Kill Chain stages +
tools), the outcome, and whether it succeeded. The next time a similar intent
arrives, the Brain recalls the most relevant successful entries and surfaces
them as context (the 'command prompt' for whatever model the user is using), and
avoids replaying failed approaches. This is how the instance evolves.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Optional

from ..config import HOME, ensure_dirs

PLAYBOOK_DIR = HOME / "brain"
PLAYBOOK_FILE = PLAYBOOK_DIR / "playbook.jsonl"
MAX_ENTRIES = 400


@dataclass
class PlaybookEntry:
    intent: str
    stage: str
    tools: list[str]
    plan_summary: str
    outcome: str
    success: bool
    artifacts: list[str] = field(default_factory=list)
    ts: str = ""
    project: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


# Patterns scrubbed from recorded outcomes so secrets never persist in the
# playbook. Bounded and conservative: it errs toward redaction.
_SECRET_PATTERNS = (
    "api_key", "apikey", "api-key", "secret", "password", "passwd", "token",
    "bearer", "authorization:", "private_key", "-----begin",
)
_SECRET_VALUE_HINTS = ("sk-", "ghp_", "gho_", "rbd_", "AKIA", "xoxb-", "Bearer ")


def scrub(text: str) -> str:
    """Redact likely secret values from a string before it is persisted.

    Bounded heuristic: matches common key names and known secret prefixes and
    replaces their values with [REDACTED]. This prevents tokens that happened to
    appear in tool output from leaking into the playbook.
    """
    if not text:
        return text
    out = text
    import re
    # key=value or key: value where the key looks like a secret name.
    for name in _SECRET_PATTERNS:
        out = re.sub(
            rf"(?i)({re.escape(name)}\s*[:=]\s*)(\S+)",
            r"\1[REDACTED]", out)
    # Bare known secret prefixes.
    for prefix in _SECRET_VALUE_HINTS:
        out = out.replace(prefix, prefix[:2] + "[REDACTED]")
    return out


def _current_project() -> str:
    """Return the active project name (engagement scope) or '' if none/global."""
    try:
        from ..projects import get_active
        active = get_active()
        return str(active) if active else ""
    except Exception:
        return ""


def record(entry: PlaybookEntry) -> None:
    """Append a playbook entry (success or failure) for future recall.

    Entries are tagged with the active project so unrelated engagements do not
    mix. Obvious secrets in the outcome are scrubbed before persistence.
    """
    ensure_dirs()
    PLAYBOOK_DIR.mkdir(parents=True, exist_ok=True)
    if not entry.ts:
        entry.ts = datetime.now().isoformat()
    if not entry.project:
        entry.project = _current_project()
    # Scrub anything that looks like a secret from the persisted fields.
    entry.outcome = scrub(entry.outcome)
    entry.plan_summary = scrub(entry.plan_summary)
    with PLAYBOOK_FILE.open("a") as f:
        f.write(json.dumps(entry.to_dict()) + "\n")
    _trim()


def _trim() -> None:
    """Keep the playbook bounded."""
    try:
        lines = PLAYBOOK_FILE.read_text().splitlines()
        if len(lines) > MAX_ENTRIES:
            PLAYBOOK_FILE.write_text("\n".join(lines[-MAX_ENTRIES:]) + "\n")
    except Exception:
        pass


def _load() -> list[dict]:
    if not PLAYBOOK_FILE.exists():
        return []
    out = []
    for line in PLAYBOOK_FILE.read_text().splitlines():
        try:
            out.append(json.loads(line))
        except Exception:
            pass
    return out


def recall(intent: str, limit: int = 5, *, project: str | None = None) -> list[dict]:
    """Keyword recall over the playbook, project-scoped by default.

    Entries from the active project rank highest (so unrelated engagements do
    not contaminate recall), then global entries (project='') as a fallback so
    the operator still benefits from cross-engagement learning when nothing in
    the current project matches.
    """
    if project is None:
        project = _current_project()
    q = (intent or "").lower()
    tokens = [t for t in q.replace("-", " ").split() if len(t) >= 3]
    scored = []
    for e in _load():
        blob = (e.get("intent", "") + " " + e.get("stage", "") + " "
                + " ".join(e.get("tools", [])) + " " + e.get("plan_summary", "")
                + " " + e.get("outcome", "")).lower()
        score = sum(1 for tok in tokens if tok in blob)
        if score > 0 or not tokens:
            # Boost same-project entries so engagements stay separate.
            same_proj = (e.get("project", "") == project) if project else True
            global_entry = not e.get("project", "")
            proj_boost = 1000 if same_proj else (100 if global_entry else 0)
            scored.append((score + proj_boost, e))
    scored.sort(key=lambda x: (x[0], x[1].get("success", False)), reverse=True)
    return [e for _, e in scored[:limit]]


def successful_tools(intent: str, limit: int = 8) -> list[str]:
    """Tools that previously succeeded for a similar intent (for the planner)."""
    seen = []
    for e in recall(intent, limit=limit * 2):
        if e.get("success"):
            for t in e.get("tools", []):
                if t not in seen:
                    seen.append(t)
        if len(seen) >= limit:
            break
    return seen


def failed_approaches(intent: str, limit: int = 4) -> list[str]:
    """Plan summaries that failed for a similar intent (to avoid replaying)."""
    out = []
    for e in recall(intent, limit=limit * 2):
        if not e.get("success") and e.get("plan_summary"):
            out.append(e["plan_summary"])
        if len(out) >= limit:
            break
    return out


def feed_forward_prompt(intent: str) -> str:
    """Compose the learned-context block the Brain injects into the model prompt.

    This is the 'evolving' signal: past successes become concrete guidance, and
    past failures become explicit 'avoid' notes.
    """
    wins = recall(intent, limit=4)
    successes = [e for e in wins if e.get("success")]
    fails = failed_approaches(intent, limit=3)
    if not successes and not fails:
        return ""
    parts = ["\n\n## Playbook (learned from your past operations)"]
    if successes:
        parts.append("What worked before for similar requests:")
        for e in successes:
            parts.append(f"- [{e.get('stage', '?')}] tools={', '.join(e.get('tools', []))}: "
                         f"{e.get('outcome', '')[:140]}")
    if fails:
        parts.append("Approaches that failed (avoid repeating):")
        for s in fails:
            parts.append(f"- {s[:140]}")
    return "\n".join(parts)


def stats() -> dict:
    """Return playbook statistics for display."""
    entries = _load()
    return {
        "total": len(entries),
        "successes": sum(1 for e in entries if e.get("success")),
        "failures": sum(1 for e in entries if not e.get("success")),
        "tools_used": sorted({t for e in entries for t in e.get("tools", [])}),
    }
