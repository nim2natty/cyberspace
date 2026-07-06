"""cyberspace swarm - the multi-agent orchestration system.

Inspired by Tandem's swarm pattern: a team of SPECIALIZED sub-agents, each with
its own role, persona, and scoped toolset, coordinated by a single Orchestrator
from one clean space. The user talks to the Orchestrator; it delegates to the
right specialist automatically.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Optional

from rich.console import Console

from .modules.base import TOOL_REGISTRY, Tool
from .agent.llm import LLMConfig, get_provider
from .agent.core import build_system_prompt

_CONSOLE = Console()


@dataclass
class SubAgentSpec:
    name: str
    display: str
    emoji: str
    role: str
    system_prompt: str
    tool_prefixes: list[str]
    tags: list[str] = field(default_factory=list)


TEAM: list[SubAgentSpec] = [
    SubAgentSpec(
        name="recon", display="Recon", emoji="\U0001f4f6",
        role="Network reconnaissance specialist",
        system_prompt=(
            "You are RECON, the team's network reconnaissance specialist. You map the "
            "target's attack surface: discover live hosts, enumerate ports and services, "
            "identify technologies using AirBender's tools and chain pipelines. "
            "Output: a structured inventory of hosts, ports, services."),
        tool_prefixes=["airbender"]),
    SubAgentSpec(
        name="exploit", display="Exploit", emoji="\U0001f40d",
        role="Exploitation specialist",
        system_prompt=(
            "You are EXPLOIT, the team's exploitation specialist. You identify "
            "vulnerabilities using all of Kali's non-networking tools (web, passwords, "
            "metasploit) and execute exploits within authorized scope. Use ShadowDragon's "
            "chain pipelines. Output: vulns found, exploits attempted, access gained."),
        tool_prefixes=["shadowdragon"]),
    SubAgentSpec(
        name="ghost", display="Ghost", emoji="\U0001f9ca",
        role="OPSEC + dark-web specialist",
        system_prompt=(
            "You are GHOST, the team's OPSEC and intelligence specialist. You manage "
            "anonymity (anti-detect, Tor, fingerprints) and conduct dark-web OSINT via "
            "IceBerg's secure tool. Choose brightside (clearnet) or darkside (Tor). "
            "Output: findings, sources, exposure assessments."),
        tool_prefixes=["iceberg"]),
    SubAgentSpec(
        name="hardware", display="Hardware", emoji="\U0001f50c",
        role="Wireless + IoT hardware operator",
        system_prompt=(
            "You are HARDWARE, the team's wireless and IoT specialist. You operate the "
            "ESP32 Marauder (802.11 attacks), FT232 serial bridge, and OpenWrt router "
            "via StickEm. Lab-scoped only. Output: wireless recon, handshakes, serial access."),
        tool_prefixes=["stickem"]),
    SubAgentSpec(
        name="smith", display="Smith", emoji="\U0001f476",
        role="AI model engineer",
        system_prompt=(
            "You are SMITH, the team's AI engineer. You train and deploy custom models "
            "with TrainABaby - datasets, GPU training, serving, plugging back into the "
            "team's brain. Output: training plans, stats, endpoints, API keys."),
        tool_prefixes=["trainababy"]),
    SubAgentSpec(
        name="scribe", display="Scribe", emoji="\U0001f4dd",
        role="Report + analysis specialist",
        system_prompt=(
            "You are SCRIBE, the team's reporting specialist. Synthesize findings from "
            "the engagement into clear, business-impact-focused reports with remediation. "
            "You read conversation history and memory to produce the deliverable."),
        tool_prefixes=[]),
]


def get_agent(name: str) -> Optional[SubAgentSpec]:
    for a in TEAM:
        if a.name == name:
            return a
    return None


def _scoped_tools(prefixes: list[str]) -> list[Tool]:
    if not prefixes:
        return []
    return [t for t in TOOL_REGISTRY.all() if any(t.name.startswith(p + ".") for p in prefixes)]


def team_brief() -> str:
    """One-line-per-agent summary for display."""
    return "\n".join(f"  {a.emoji} {a.display:<10} {a.role}" for a in TEAM)


ORCHESTRATOR_SYSTEM = """You are the ORCHESTRATOR, the mission commander of the cyberspace agent swarm.

You lead a team of SPECIALIZED sub-agents. You do NOT run tools yourself - you DELEGATE to the right specialist. Your single tool is `swarm.delegate`.

## Your team
- **Recon** (📶): network reconnaissance. Call for: scanning, enumeration, mapping attack surface.
- **Exploit** (🐍): exploitation - web, creds, metasploit. Call for: attacking services, web testing.
- **Ghost** (🧊): OPSEC + dark-web intelligence. Call for: staying hidden, dark-web OSINT.
- **Hardware** (🔌): wireless/IoT - ESP32, FT232, router. Call for: WiFi attacks, serial, lab hardware.
- **Smith** (👶): AI engineering. Call for: training a custom model, deploying an endpoint.
- **Scribe** (📝): reporting. Call for: when engagement is done and you need a deliverable.

## How to operate
1. Understand the objective. 2. Break it into phases and delegate each to the RIGHT specialist.
3. Chain their outputs (Recon finds web app -> Exploit tests it -> Scribe reports).
4. Stay within authorized scope. 5. When done, delegate to Scribe for the report.
"""


class Swarm:
    """The multi-agent team. Orchestrator delegates; sub-agents execute."""

    def __init__(self, cfg: LLMConfig, console: Optional[Console] = None):
        self.cfg = cfg
        self.console = console or _CONSOLE
        self.messages = [{"role": "system", "content": build_system_prompt(ORCHESTRATOR_SYSTEM)}]
        self.max_iterations = 20
        self.provider = get_provider(cfg)
        self.agent_logs = {a.name: [] for a in TEAM}

    def _delegate_tool(self) -> Tool:
        def _fn(agent_name="", task=""):
            return self.delegate(agent_name, task)
        return Tool(name="swarm.delegate",
            description="Delegate a task to a specialized sub-agent. Agents: " +
            ", ".join(f"{a.name} ({a.role})" for a in TEAM),
            parameters={"type": "object", "properties": {
                "agent_name": {"type": "string", "description": "one of: " + ", ".join(a.name for a in TEAM)},
                "task": {"type": "string"}}, "required": ["agent_name", "task"]}, fn=_fn)

    def delegate(self, agent_name: str, task: str) -> str:
        spec = get_agent(agent_name)
        if not spec:
            return f"ERROR: no agent '{agent_name}'. Team: {', '.join(a.name for a in TEAM)}"
        self.console.print(f"   [dim]delegating to[/dim] {spec.emoji} "
                           f"[bold magenta]{spec.display}[/bold magenta]: {task[:80]}")
        if not spec.tool_prefixes:
            from .memory import context_block, recent_episodes
            ctx = "Recent engagement activity:\n"
            for ep in recent_episodes(30):
                ctx += f"- [{ep.get('platform','')}] {ep.get('action','')}: {ep.get('result_summary','')[:120]}\n"
            return self._freeform(spec, task, ctx + "\n" + context_block())
        return self._run_subagent(spec, task)

    def _run_subagent(self, spec: SubAgentSpec, task: str) -> str:
        tools = _scoped_tools(spec.tool_prefixes)
        messages = [{"role": "system", "content": build_system_prompt(spec.system_prompt)},
                    {"role": "user", "content": task}]
        result = ""
        for _ in range(10):
            resp = get_provider(self.cfg).chat(messages, tools)
            m = {"role": "assistant", "content": resp.text}
            if resp.tool_calls:
                m["tool_calls"] = [{"id": f"call_{i}", "type": "function",
                     "function": {"name": c.name, "arguments": json.dumps(c.arguments)}}
                    for i, c in enumerate(resp.tool_calls)]
            messages.append(m)
            if not resp.tool_calls:
                result = resp.text; break
            for call in resp.tool_calls:
                tool = next((t for t in tools if t.name == call.name), None)
                if not tool:
                    out = f"ERROR: '{call.name}' not available to {spec.display}"
                else:
                    self.console.print(f"      [dim]{spec.display} calls[/dim] [cyan]{call.name}[/cyan]")
                    try:
                        out = str(tool.fn(**call.arguments))
                        from .memory import record
                        record(spec.name, call.name, call.arguments, out[:300])
                    except Exception as e:
                        out = f"ERROR: {e}"
                messages.append({"role": "tool", "name": call.name, "content": out})
        else:
            result = result or "(sub-agent reached its tool limit)"
        self.agent_logs[spec.name].append(f"Task: {task}\nResult: {result[:500]}")
        self.console.print(f"   [dim]{spec.emoji} {spec.display} done[/dim]")
        return result[:4000]

    def _freeform(self, spec: SubAgentSpec, task: str, context: str) -> str:
        messages = [{"role": "system", "content": build_system_prompt(spec.system_prompt)},
                    {"role": "user", "content": context + "\n\nTask: " + task}]
        resp = get_provider(self.cfg).chat(messages, [])
        self.agent_logs[spec.name].append(f"Task: {task}\nResult: {resp.text[:500]}")
        return resp.text

    def ask(self, prompt: str) -> str:
        self.messages.append({"role": "user", "content": prompt})
        dt = self._delegate_tool()
        for _ in range(self.max_iterations):
            resp = self.provider.chat(self.messages, [dt])
            m = {"role": "assistant", "content": resp.text}
            if resp.tool_calls:
                m["tool_calls"] = [{"id": f"call_{i}", "type": "function",
                     "function": {"name": c.name, "arguments": json.dumps(c.arguments)}}
                    for i, c in enumerate(resp.tool_calls)]
            self.messages.append(m)
            if not resp.tool_calls:
                self.console.print()
                self.console.print(f"[green]orchestrator>[/green] {resp.text}")
                return resp.text
            for call in resp.tool_calls:
                if call.name == "swarm.delegate":
                    result = self.delegate(call.arguments.get("agent_name", ""),
                                           call.arguments.get("task", ""))
                else:
                    result = "ERROR: orchestrator can only use swarm.delegate"
                self.messages.append({"role": "tool", "name": call.name, "content": result})
        self.console.print("[yellow](orchestrator reached delegation limit)[/yellow]")
        return ""
