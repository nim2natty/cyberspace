"""cyberspace memory - the personalization layer.

Every platform records what it does here (episodic memory). Over time the system
also builds a user-profile: the operator's preferred tools, common targets, skill
level, and recurring intents. That profile is injected into the agent's system
prompt so cyberbot needs fewer prompts to act - it remembers the operator across
sessions.

Three stores, persisted to ~/.cyberspace/memory/:
  episodes.jsonl  - append-only log of {platform, action, args, summary, ts}
  semantic.json   - distilled facts learned about the operator's environment
  profile.json    - the evolving user profile (preferences, patterns, skill)
"""
from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path

from .config import HOME, ensure_dirs

MEM_DIR = HOME / "memory"
EPISODES_FILE = MEM_DIR / "episodes.jsonl"
SEMANTIC_FILE = MEM_DIR / "semantic.json"
PROFILE_FILE = MEM_DIR / "profile.json"

MAX_EPISODES = 500
MAX_PROFILE_FACTS = 60


@dataclass
class UserProfile:
    """The learned profile, injected into the agent's system prompt."""
    skill_level: str = "intermediate"          # beginner | intermediate | advanced
    preferred_platforms: list[str] = field(default_factory=list)
    preferred_tools: list[str] = field(default_factory=list)
    common_targets: list[str] = field(default_factory=list)
    common_intents: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    last_updated: str = ""

    def to_prompt(self) -> str:
        """Render the profile as a concise context block for the system prompt."""
        parts = ["\n\n## Operator profile (learned - use to need fewer prompts)"]
        parts.append(f"Skill level: {self.skill_level}.")
        if self.preferred_platforms:
            parts.append(f"Frequently uses: {', '.join(self.preferred_platforms[:5])}.")
        if self.preferred_tools:
            parts.append(f"Preferred tools: {', '.join(self.preferred_tools[:8])}.")
        if self.common_targets:
            parts.append(f"Usual targets: {', '.join(self.common_targets[:5])}.")
        if self.common_intents:
            parts.append(f"Common tasks: {', '.join(self.common_intents[:5])}.")
        if self.notes:
            parts.append("Notes: " + "; ".join(self.notes[:6]))
        parts.append("Tailor explanations to the skill level and default to the preferred "
                     "tools/platforms when the intent matches.")
        return "\n".join(parts)


def _load_json(path: Path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text())
    except Exception:
        return default


def _save_json(path: Path, data) -> None:
    ensure_dirs()
    MEM_DIR.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, default=str))


def _episodes() -> list[dict]:
    if not EPISODES_FILE.exists():
        return []
    out = []
    for line in EPISODES_FILE.read_text().splitlines()[-MAX_EPISODES:]:
        try:
            out.append(json.loads(line))
        except Exception:
            pass
    return out


def record(platform: str, action: str, args: dict | None = None,
           result_summary: str = "", intent: str = "") -> None:
    """Append an episode. Called by every platform after an action."""
    ensure_dirs()
    MEM_DIR.mkdir(parents=True, exist_ok=True)
    ep = {"ts": datetime.now().isoformat(), "platform": platform, "action": action,
          "args": args or {}, "result_summary": (result_summary or "")[:300], "intent": intent}
    with EPISODES_FILE.open("a") as f:
        f.write(json.dumps(ep) + "\n")
    _update_profile_incremental(platform, action, args or {}, intent)


def _update_profile_incremental(platform: str, action: str, args: dict, intent: str) -> None:
    p = load_profile()
    changed = False
    if platform and platform not in p.preferred_platforms:
        p.preferred_platforms.insert(0, platform); p.preferred_platforms = p.preferred_platforms[:10]
        changed = True
    tool = args.get("tool") or args.get("name") or action
    if tool and tool not in p.preferred_tools:
        p.preferred_tools.insert(0, str(tool)); p.preferred_tools = p.preferred_tools[:12]
        changed = True
    target = args.get("target") or args.get("url") or args.get("domain") or ""
    if target and str(target) not in p.common_targets:
        p.common_targets.insert(0, str(target)); p.common_targets = p.common_targets[:10]
        changed = True
    if intent and intent not in p.common_intents:
        p.common_intents.insert(0, intent); p.common_intents = p.common_intents[:10]
        changed = True
    if changed:
        p.last_updated = datetime.now().isoformat()
        _save_json(PROFILE_FILE, asdict(p))


def load_profile() -> UserProfile:
    d = _load_json(PROFILE_FILE, {})
    return UserProfile(**{k: d[k] for k in UserProfile.__dataclass_fields__ if k in d})


def save_profile(p: UserProfile) -> None:
    p.last_updated = datetime.now().isoformat()
    _save_json(PROFILE_FILE, asdict(p))


def set_skill_level(level: str) -> None:
    p = load_profile(); p.skill_level = level; save_profile(p)


def add_note(note: str) -> None:
    p = load_profile()
    if note and note not in p.notes:
        p.notes.insert(0, note); p.notes = p.notes[:MAX_PROFILE_FACTS]
        save_profile(p)


def semantic_fact(key: str, value: str) -> None:
    """Record a learned fact about the environment (e.g. 'lab_subnet': '10.10.10.0/24')."""
    facts = _load_json(SEMANTIC_FILE, {})
    facts[key] = {"value": value, "ts": datetime.now().isoformat()}
    _save_json(SEMANTIC_FILE, facts)


def context_block() -> str:
    """The full memory context to inject into the agent system prompt."""
    p = load_profile()
    facts = _load_json(SEMANTIC_FILE, {})
    block = p.to_prompt()
    if facts:
        env = "; ".join(f"{k}={v['value']}" for k, v in list(facts.items())[:10])
        block += f"\nKnown environment: {env}."
    return block


def recent_episodes(limit: int = 20) -> list[dict]:
    return _episodes()[-limit:]


def top_tools(n: int = 8) -> list[tuple[str, int]]:
    c = Counter()
    for e in _episodes():
        tool = e.get("args", {}).get("tool") or e.get("action", "")
        if tool:
            c[str(tool)] += 1
    return c.most_common(n)


def recall(query: str, limit: int = 5) -> list[dict]:
    """Simple keyword recall over episodes (helps the agent reference history)."""
    q = query.lower()
    scored = []
    for e in _episodes():
        blob = (e.get("action", "") + " " + e.get("result_summary", "")
                + " " + json.dumps(e.get("args", {}))).lower()
        if q in blob:
            scored.append(e)
    return scored[-limit:]

