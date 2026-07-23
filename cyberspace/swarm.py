"""cyberspace swarm - Cyber Kill Chain orchestration.

The swarm operates on the Lockheed Martin Cyber Kill Chain: seven chronological
stages that describe a complete attack lifecycle. Cyberspace maps the operator's
objective to the right stage and runs the corresponding specialist with scoped tools.

    1. Reconnaissance  -  map the attack surface
    2. Weaponization   -  build payloads, select exploits
    3. Delivery        -  transmit the weapon to the target
    4. Exploitation    -  trigger the vulnerability
    5. Installation    -  deploy persistence / implants
    6. C2              -  establish command and control
    7. Actions on Obj  -  achieve the objective; LOG everything here

Every prompt the user types is recorded as "Actions on Objectives" memory so the
system learns how the operator runs attacks and can cross-reference techniques.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Optional

from rich.console import Console

from .modules.base import TOOL_REGISTRY, Tool
from .agent.llm import LLMConfig, get_provider, ProviderError, chat_with_failover
from .agent.core import build_system_prompt
from .tooling import BATCH_PLANNING_INSTRUCTIONS
from .success import assess_tool_output, tool_contract_text

_CONSOLE = Console()


@dataclass
class KillChainStage:
    name: str
    display: str
    emoji: str
    role: str
    system_prompt: str
    tool_prefixes: list[str]
    phase: int  # 1-7 for chronological ordering


# The seven stages of the Cyber Kill Chain. Each maps to a toolset.
KILL_CHAIN: list[KillChainStage] = [
    KillChainStage(
        name="recon", display="Reconnaissance", emoji="\U0001f50d", phase=1,
        role="Map the target's attack surface",
        system_prompt=(
            "You are the RECONNAISSANCE stage of the Cyber Kill Chain. Your job is to "
            "map the target's attack surface: discover live hosts, enumerate open ports, "
            "identify running services and technologies. Use AirBender's networking "
            "tools (nmap, masscan, ping-sweep, dig, whois). Be FAST: prefer quick scans "
            "(top-ports, -T5, no DNS) over exhaustive ones. Output: a structured "
            "inventory of hosts, ports, services found."),
        tool_prefixes=["airbender"]),
    KillChainStage(
        name="weapon", display="Weaponization", emoji="\U0001f9a0", phase=2,
        role="Build payloads and select exploits",
        system_prompt=(
            "You are the WEAPONIZATION stage of the Cyber Kill Chain. Based on "
            "reconnaissance findings, you craft the attack: search for exploits "
            "(searchsploit), build payloads (msfvenom), prepare web-attack payloads "
            "(sqlmap, gobuster), and select the right exploit modules. Use "
            "ShadowDragon's catalog. Output: the weapon ready for delivery."),
        tool_prefixes=["shadowdragon"]),
    KillChainStage(
        name="delivery", display="Delivery", emoji="\U0001f4e7", phase=3,
        role="Transmit the weapon to the target",
        system_prompt=(
            "You are the DELIVERY stage of the Cyber Kill Chain. You transmit the "
            "crafted weapon to the target. This includes browsing target web apps with "
            "the IceBerg stealth browser, delivering payloads via web requests, or "
            "using social-engineering vectors. Use IceBerg's OPSEC browser to interact "
            "with targets while staying hidden. Output: confirmation of delivery."),
        tool_prefixes=["iceberg"]),
    KillChainStage(
        name="exploit", display="Exploitation", emoji="\U0001f4a5", phase=4,
        role="Trigger the vulnerability",
        system_prompt=(
            "You are the EXPLOITATION stage of the Cyber Kill Chain. You trigger the "
            "vulnerability to gain access. Run exploits (metasploit), SQL injection "
            "(sqlmap), web attacks (nikto, gobuster), and credential attacks. Use "
            "ShadowDragon's full-assault chain. Output: access gained, vulns exploited."),
        tool_prefixes=["shadowdragon"]),
    KillChainStage(
        name="install", display="Installation", emoji="\U0001f4e1", phase=5,
        role="Deploy persistence and implants",
        system_prompt=(
            "You are the INSTALLATION stage of the Cyber Kill Chain. You deploy "
            "persistence mechanisms: backdoors, hardware implants, or persistent access "
            "on compromised routers/IoT. Use StickEm to operate the ESP32 Marauder, FT232 "
            "serial bridge, or OpenWrt router for hardware-level installation. "
            "Output: persistent access established."),
        tool_prefixes=["stickem"]),
    KillChainStage(
        name="c2", display="Command & Control (C2)", emoji="\U0001f5f3", phase=6,
        role="Establish covert command channels",
        system_prompt=(
            "You are the COMMAND & CONTROL stage of the Cyber Kill Chain. You establish "
            "covert communication channels with the target: Tor-based C2, encrypted "
            "channels, OPSEC hardening. Use IceBerg's anonymity tools (Tor, anti-detect "
            "profiles, proxychains). Output: C2 channel established."),
        tool_prefixes=["iceberg"]),
    KillChainStage(
        name="objectives", display="Actions on Objectives", emoji="\U0001f3af", phase=7,
        role="Achieve the objective + log everything",
        system_prompt=(
            "You are the ACTIONS ON OBJECTIVES stage of the Cyber Kill Chain. The attack "
            "path is complete; now achieve the goal. This includes data collection, "
            "reporting, and CRITICALLY: logging the full attack narrative so it becomes "
            "cross-referencable memory for future operations. Use RoboDaddy for custom "
            "model needs. Synthesize all findings into a clear report. Output: the "
            "objective achieved + a full kill-chain narrative."),
        tool_prefixes=["robodaddy"]),
]


def _criterion_lines(value: str) -> list[str]:
    return [line.strip().lstrip("-*0123456789. ").strip()
            for line in re.split(r"[;\n]+", value or "")
            if line.strip().lstrip("-*0123456789. ").strip()]


def _verified_stage_result(result: str, criteria: str) -> tuple[bool, str]:
    """Require a verdict and evidence marker for every delegated criterion."""
    rows = _criterion_lines(criteria)
    text = result or ""
    verdicts = re.findall(r"(?im)\b(?:pass|fail|uncertain|not-tested)\b", text)
    evidence = re.findall(r"(?im)\bevidence\s*:", text)
    if rows and len(verdicts) >= len(rows) and len(evidence) >= len(rows):
        return True, text
    return False, ("STAGE UNCERTAIN: specialist response did not provide one explicit "
                   "pass/fail/uncertain/not-tested verdict and evidence entry per criterion.\n"
                   f"Criteria ({len(rows)}): {criteria}\nRaw response: {text or '(empty)'}")

KILL_CHAIN_STAGES = [s.name for s in KILL_CHAIN]


def get_stage(name: str) -> Optional[KillChainStage]:
    for s in KILL_CHAIN:
        if s.name == name:
            return s
    return None


def _scoped_tools(prefixes: list[str]) -> list[Tool]:
    if not prefixes:
        return []
    return [t for t in TOOL_REGISTRY.all() if any(t.name.startswith(p + ".") for p in prefixes)]


def kill_chain_brief() -> str:
    """One-line-per-stage summary for display."""
    return "\n".join(f"  {s.phase}. {s.emoji} {s.display:<22} {s.role}" for s in KILL_CHAIN)


# Backwards compat: old code referenced TEAM/team_brief/get_agent
TEAM = KILL_CHAIN


def get_agent(name: str):
    return get_stage(name)


def team_brief() -> str:
    return kill_chain_brief()


_STAGE_KEYWORDS = {
    "recon": ["scan", "discover", "find", "map", "enumerate", "ping", "nmap", "host",
              "device", "network", "port", "service", "who is on", "what's on",
              "what devices", "what services", "live host", "subnet"],
    "weapon": ["exploit", "payload", "prepare", "build", "craft", "searchsploit",
               "msfvenom", "weapon", "select exploit"],
    "delivery": ["deliver", "send", "browse", "navigate", "open url", "visit",
                 "phishing", "social engineer", "inject web", "post to"],
    "exploit": ["run exploit", "attack", "inject", "sql injection", "sqlmap",
                "metasploit", "msfconsole", "brute force", "crack", "break in",
                "gain access", "full assault", "vulnerability test"],
    "install": ["install", "persistent", "backdoor", "implant", "deploy",
                "hardware", "serial", "router", "openwrt", "marauder"],
    "c2": ["c2", "command and control", "tor", "anonymous", "covert",
           "proxy", "hidden channel", "reverse shell", "beacon"],
    "objectives": ["report", "summarize", "objective", "exfiltrate", "collect",
                   "what did we find", "results", "findings", "write up"],
}


def detect_stage(prompt: str) -> str:
    """Detect which kill chain stage the user's prompt maps to."""
    p = (prompt or "").lower()
    best, best_score = "recon", 0
    for stage, keywords in _STAGE_KEYWORDS.items():
        # Longer phrases are more specific than a shared single word (for
        # example "run exploit" belongs to exploitation, not weaponization).
        score = sum(len(kw.split()) for kw in keywords
                    if re.search(r"(?<!\w)" + re.escape(kw) + r"(?!\w)", p))
        if score > best_score:
            best, best_score = stage, score
    return best


WORKFLOW_SYSTEM = """You are cyberspace, a Cyber Kill Chain workflow engine.

You operate on the 7-stage Lockheed Martin Cyber Kill Chain. You map the operator's
objective to the correct stage and delegate to the specialist for that stage.

## The Cyber Kill Chain (7 chronological stages)
1. **Reconnaissance**: Map the attack surface. Use for: scanning, host discovery, port enumeration.
2. **Weaponization**: Build payloads, select exploits. Use for: finding exploits, crafting payloads.
3. **Delivery**: Transmit the weapon. Use for: browsing targets, web delivery.
4. **Exploitation**: Trigger the vulnerability. Use for: running exploits, SQL injection, brute force.
5. **Installation**: Deploy persistence/implants. Use for: backdoors, hardware, router access.
6. **Command & Control**: Establish covert channels. Use for: Tor, anonymity, reverse shells.
7. **Actions on Objectives**: Achieve the goal + log everything. Use for: reporting, data collection.

## You choose the attack vector and stage
When the user describes a goal in plain language, DO NOT ask them which tool or stage
to use. Map it to the correct kill chain stage and delegate. Run it. Explain results
in plain language, stating WHICH STAGE of the kill chain you're in.

Before delegating, make the objective's measurable acceptance criteria explicit.
Pass those criteria to the specialist. Do not mark a stage complete merely because
a tool ran: require evidence and a pass/fail/uncertain verdict for each criterion.

## Speed and coverage are critical
Prefer FAST operations. For local-network inventory, use airbender.chain with the
local-recon pipeline so independent discovery methods run concurrently and results are
cross-checked; do not rely on nmap alone. Do not run exhaustive scans unless requested.

## You manage projects
If the user mentions a topic matching an existing project, call project.search to find
it, project.open to switch to it, or project.create if none exists. Prompts are
auto-saved to the active project as Actions on Objectives memory.
"""


class Swarm:
    """Execute requests through the seven-stage Cyber Kill Chain."""

    def __init__(self, cfg: LLMConfig, console: Optional[Console] = None,
                 ghost_mode: bool = False):
        self.cfg = cfg
        self.console = console or _CONSOLE
        self.ghost_mode = ghost_mode
        self.messages = [{"role": "system", "content": build_system_prompt(WORKFLOW_SYSTEM)}]
        self.provider = get_provider(cfg)
        self.agent_logs = {s.name: [] for s in KILL_CHAIN}
        self.current_stage = ""

    def _delegate_tool(self) -> Tool:
        def _fn(agent_name="", task="", success_criteria=""):
            return self.delegate(agent_name, task, success_criteria)
        return Tool(name="swarm.delegate",
            description="Delegate a task to a Cyber Kill Chain stage. Stages: " +
            ", ".join(f"{s.name} ({s.display})" for s in KILL_CHAIN),
            parameters={"type": "object", "properties": {
                "agent_name": {"type": "string", "description": "kill chain stage: " +
                 ", ".join(s.name for s in KILL_CHAIN)},
                "task": {"type": "string", "description": "the specific task for this stage"},
                 "success_criteria": {"type": "string", "description":
                    "measurable acceptance criteria, one per line, including required evidence"}},
                "required": ["agent_name", "task", "success_criteria"]},
            fn=_fn)

    def delegate(self, stage_name: str, task: str, success_criteria: str = "") -> str:
        """Delegate a task to the named kill chain stage specialist."""
        spec = get_stage(stage_name)
        if not spec:
            return (f"ERROR: unknown kill chain stage '{stage_name}'. "
                    f"Available: {', '.join(s.name for s in KILL_CHAIN)}")
        self.current_stage = spec.name
        self.console.print(
            f"\n  {spec.emoji} [bold yellow]STAGE {spec.phase}: {spec.display}[/bold yellow]")
        self.console.print(f"  [dim]Task: {task[:120]}[/dim]\n")
        tools = _scoped_tools(spec.tool_prefixes)
        criteria = success_criteria.strip() or (
            f"Complete this {spec.display} task in scope; return substantive evidence, "
            "explicitly label pass/fail/uncertain, and disclose errors or untested items.")
        delegated = (f"<task>{task}</task>\n<success_criteria>{criteria}</success_criteria>\n"
                     "Return the complete precise command list in this response. Select the "
                     "smallest bounded set that directly produces the requested information.")
        messages = [{"role": "system", "content": build_system_prompt(
                        spec.system_prompt + "\n\n" + BATCH_PLANNING_INSTRUCTIONS)},
                    {"role": "user", "content": delegated}]
        try:
            resp = chat_with_failover(self.provider, messages, tools, self.console)
        except ProviderError as e:
            self.console.print(f"  [red]{spec.display} error: {e}[/red]")
            return f"STAGE ERROR ({spec.display}): {e}"
        if resp.tool_calls:
            from .tooling import execute_tool_batch
            from .cyberdeck.criteria import evaluate_stage
            def record_command(command, output):
                from .memory import record
                record(spec.name, command.tool, command.arguments, output[:300])
            result, executions = execute_tool_batch(
                resp.tool_calls, tools, task, console=self.console, stage=spec.name,
                recorder=record_command)
            stage_results = evaluate_stage(
                spec.name, "\n\n".join(row.evidence for row in executions))
            verified = (bool(executions) and all(row.status == "pass" for row in executions)
                        and bool(stage_results)
                        and all(row.status == "pass" for row in stage_results))
        else:
            verified, result = _verified_stage_result(resp.text, criteria)
        self.agent_logs[spec.name].append(f"Task: {task}\nResult: {result[:500]}")
        state = "verified" if verified else "uncertain"
        self.console.print(f"  [dim]{spec.emoji} {spec.display} {state}[/dim]\n")
        # Record this stage's outcome in Actions on Objectives memory.
        self._record_objective(spec, task, result)
        return result

    def _record_objective(self, spec: KillChainStage, task: str, result: str) -> None:
        """Save every kill-chain action as cross-referenceable objective memory."""
        try:
            from .memory import record
            record(platform="kill_chain", action=f"{spec.phase}_{spec.name}",
                   args={"stage": spec.display, "task": task},
                   result_summary=result[:300], intent=spec.name)
        except Exception:
            pass

    def ask(self, prompt: str) -> str:
        """Route once, plan once in the scoped stage, then execute a command batch."""
        from .cyberdeck.prompts import record_prompt, complete_prompt
        prompt_record = record_prompt(
            prompt, source="swarm-ghost" if self.ghost_mode else "swarm")
        # Refresh project-scoped Actions-on-Objectives memory every turn.
        self.messages[0]["content"] = build_system_prompt(WORKFLOW_SYSTEM)
        # Detect and announce the stage for the user's benefit.
        stage = detect_stage(prompt)
        spec = get_stage(stage)
        if spec:
            self.console.print(f"\n  [bold magenta]>> Kill Chain stage detected: "
                               f"{spec.emoji} {spec.display} (phase {spec.phase})[/bold magenta]\n")
        # Record prompt as Actions on Objectives memory.
        if not self.ghost_mode:
            self._save_objective_prompt(prompt)
        try:
            response = self.delegate(stage, prompt)
        except Exception as exc:
            complete_prompt(prompt_record["sequence"], str(exc), status="failed")
            raise
        self.console.print()
        self.console.print(
            f"[green]cyberspace [{spec.display if spec else 'Kill Chain'}]>[/green] {response}")
        self._save_to_project(prompt, response)
        complete_prompt(prompt_record["sequence"], response)
        return response

    @staticmethod
    def _assistant_msg(resp) -> dict:
        msg = {"role": "assistant", "content": resp.text}
        if resp.tool_calls:
            msg["tool_calls"] = [
                {"id": c.id or f"call_{i}", "type": "function",
                 "function": {"name": c.name, "arguments": json.dumps(c.arguments)}}
                for i, c in enumerate(resp.tool_calls)]
        return msg

    def _save_objective_prompt(self, prompt: str) -> None:
        """Record the user's prompt as Actions on Objectives memory."""
        try:
            from .memory import record
            record(platform="kill_chain", action="user_objective",
                   args={"prompt": prompt}, result_summary="", intent="user_input")
        except Exception:
            pass

    def _save_to_project(self, prompt: str, response: str) -> None:
        """Auto-save this prompt+response to the active project."""
        if self.ghost_mode:
            return
        try:
            from .projects import get_active, add_prompt
            active = get_active()
            if active:
                add_prompt(active, prompt, response, source="kill_chain")
        except Exception:
            pass
