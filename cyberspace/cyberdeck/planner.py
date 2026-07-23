"""The Cyberdeck's planner: decompose a request into a multi-tool Kill Chain plan.

Given a plain-language objective, the planner produces a list of tasks. Each task
maps to a Cyber Kill Chain stage and names MULTIPLE tools to run for that task
(independent methods can cross-check the same target). It
uses the configured AI provider when available, with a deterministic heuristic
fallback so the Cyberdeck always produces a usable plan.

Example: 'find devices on this network' ->
  recon:  airbender ping-sweep + airbender nmap + airbender arp scan
          (then) capture packets with shadowdragon tshark/tcpdump per host
  objectives: compile device inventory + packet links into a report
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Optional

from ..swarm import KILL_CHAIN, detect_stage


@dataclass
class CyberdeckTask:
    stage: str
    description: str
    tools: list[str]
    depends_on: list[str] = field(default_factory=list)
    parallel: bool = True

    def to_dict(self) -> dict:
        return {"stage": self.stage, "description": self.description, "tools": self.tools,
                "depends_on": self.depends_on, "parallel": self.parallel}


@dataclass
class CyberdeckPlan:
    intent: str
    detected_stage: str
    tasks: list[CyberdeckTask] = field(default_factory=list)
    missing_tools: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {"intent": self.intent, "detected_stage": self.detected_stage,
                "tasks": [t.to_dict() for t in self.tasks], "missing_tools": self.missing_tools}


def _provider():
    try:
        from ..agent.config import load_config
        from ..agent.llm import get_provider
        cfg = load_config()
        if not cfg:
            return None
        return get_provider(cfg)
    except Exception:
        return None


def _parse_json(text: str):
    t = (text or "").strip().removeprefix("```json").removesuffix("```").strip()
    start, end = t.find("["), t.rfind("]")
    if start >= 0 and end > start:
        t = t[start:end + 1]
    try:
        return json.loads(t)
    except Exception:
        return []


def plan(intent: str, *, max_tasks: int = 6, use_ai: bool = False) -> CyberdeckPlan:
    """Build a multi-tool Kill Chain plan for a request.

    Uses the deterministic planner by default so execution never waits for a
    provider merely to select a known tool. AI decomposition remains available
    explicitly for callers that want an open-ended plan.
    """
    detected = detect_stage(intent)
    provider = _provider() if use_ai else None
    if provider is not None:
        ai_tasks = _ai_plan(provider, intent, detected)
        if ai_tasks:
            return CyberdeckPlan(intent=intent, detected_stage=detected, tasks=ai_tasks)
    return heuristic_plan(intent, detected, max_tasks=max_tasks)


def _ai_plan(provider, intent: str, detected: str) -> list[CyberdeckTask]:
    """Ask the provider to decompose the objective into multi-tool tasks."""
    from .playbook import successful_tools, failed_approaches
    known_tools = _known_tool_names()
    wins = successful_tools(intent)
    avoid = failed_approaches(intent)
    parts = [
        "You plan authorized security operations on the Cyber Kill Chain. Decompose the "
        "objective into 1-6 chronological tasks. Each task maps to a stage "
        "(recon, weapon, delivery, exploit, install, c2, objectives) and names MULTIPLE "
        "tools from the available list (cross-check independent methods for the most "
        "cross-checked result). Return ONLY a JSON array of objects with keys: "
        "stage, description, tools (array), depends_on (array of prior task indices), "
        "parallel (bool).",
        "",
        "Objective: " + str(intent),
        "Detected starting stage: " + str(detected),
        "Available tools: " + json.dumps(known_tools[:120]),
    ]
    if wins:
        parts.append("Tools that succeeded for similar requests before: " + json.dumps(wins))
    if avoid:
        parts.append("Avoid these previously-failed approaches: " + json.dumps(avoid[:3]))
    try:
        resp = provider.chat([
            {"role": "system", "content": "You return only a JSON array of plan tasks."},
            {"role": "user", "content": "\n".join(parts)}], [])
        raw = _parse_json(resp.text)
        tasks = []
        for item in raw if isinstance(raw, list) else []:
            tools = [str(t) for t in item.get("tools", []) if str(t) in known_tools or _looks_like_tool(t)]
            if not tools:
                continue
            tasks.append(CyberdeckTask(
                stage=str(item.get("stage", "recon")),
                description=str(item.get("description", ""))[:300],
                tools=tools,
                depends_on=[int(d) for d in item.get("depends_on", []) if str(d).isdigit()],
                parallel=bool(item.get("parallel", True))))
        return tasks[:6]
    except Exception:
        return []


def _known_tool_names() -> list[str]:
    """Collect every registered tool name plus the catalog tool names."""
    names = []
    try:
        from ..modules.base import TOOL_REGISTRY
        names = [t.name for t in TOOL_REGISTRY.all()]
    except Exception:
        pass
    try:
        from ..platforms.shadowdragon.catalog import all_tools
        names += ["shadowdragon.kali_run::" + t for t in all_tools()]
    except Exception:
        pass
    return sorted(set(names))


def _looks_like_tool(name) -> bool:
    """Allow ShadowDragon generic Kali runner names like 'shadowdragon.kali_run::nmap'."""
    s = str(name)
    return "." in s or "::" in s


# ---------------------------------------------------------------------------
# Deterministic heuristic planner (fallback + default)
# ---------------------------------------------------------------------------
def heuristic_plan(intent: str, detected: str, *, max_tasks: int = 5) -> CyberdeckPlan:
    """Build a sensible multi-tool plan from keyword matching against the catalogs."""
    text = (intent or "").lower()
    tasks: list[CyberdeckTask] = []

    if any(k in text for k in ("device", "host", "network", "subnet", "who is on", "find devices")):
        # A device inventory is discovery, not a full port/service/capture job.
        # local-discovery cross-checks installed probes concurrently without the
        # overlapping ping-sweep + nmap + full chain formerly scheduled here.
        tasks.append(CyberdeckTask(
            stage="recon",
            description="Discover live devices using installed local-network probes.",
            tools=["airbender.chain"],
            parallel=True))
        tasks.append(CyberdeckTask(
            stage="objectives",
            description="Compile the discovered device inventory into one report.",
            tools=["cyberdeck.report"],
            depends_on=[0], parallel=False))

    elif any(k in text for k in ("web", "website", "url", "app", "sql", "login")):
        tasks.append(CyberdeckTask(
            stage="recon",
            description="Identify the web technology and map its surface.",
            tools=["shadowdragon.whatweb", "shadowdragon.gobuster", "shadowdragon.nikto"],
            parallel=True))
        tasks.append(CyberdeckTask(
            stage="exploit",
            description="Test for the highest-impact web weaknesses.",
            tools=["shadowdragon.kali_run::nuclei", "shadowdragon.sqlmap"],
            depends_on=[0], parallel=True))
        tasks.append(CyberdeckTask(
            stage="objectives",
            description="Compile findings into a prioritized report.",
            tools=["cyberdeck.report"],
            depends_on=[1], parallel=False))

    elif any(k in text for k in ("password", "crack", "hash", "brute")):
        tasks.append(CyberdeckTask(
            stage="exploit",
            description="Attempt credential recovery with multiple engines and wordlists.",
            tools=["shadowdragon.hashcat", "shadowdragon.john", "shadowdragon.hydra"],
            parallel=True))
        tasks.append(CyberdeckTask(
            stage="objectives",
            description="Summarize recovered credentials and recommendations.",
            tools=["cyberdeck.report"], depends_on=[0], parallel=False))

    else:
        # Generic: map the detected stage and give it the stage's toolset + a report.
        stage = detected or "recon"
        tools = _default_tools_for_stage(stage)
        tasks.append(CyberdeckTask(
            stage=stage, description="Run the specialist toolset for this objective.",
            tools=tools, parallel=True))
        tasks.append(CyberdeckTask(
            stage="objectives", description="Compile results into an evidence report.",
            tools=["cyberdeck.report"], depends_on=[0], parallel=False))

    return CyberdeckPlan(intent=intent, detected_stage=detected, tasks=tasks[:max_tasks])


def _default_tools_for_stage(stage: str) -> list[str]:
    """Default toolset for a stage when no specific heuristic matched."""
    defaults = {
        "recon": ["airbender.ping_sweep", "airbender.nmap", "airbender.dig"],
        "weapon": ["shadowdragon.searchsploit"],
        "delivery": ["iceberg.browse"],
        "exploit": ["shadowdragon.kali_run::nuclei", "shadowdragon.sqlmap"],
        "install": ["shadowdragon.kali_run::msfconsole"],
        "c2": ["iceberg.find"],
        "objectives": ["cyberdeck.report"],
    }
    return defaults.get(stage, ["cyberdeck.report"])
