"""The cyberbot agent core - the tool-calling ReAct loop.

Flow:
  user msg -> LLM (with all module tools) -> [tool_calls] -> execute tools ->
  feed results back -> LLM -> ... -> final text answer.

This is the single control plane. Every module's tools are available here, so
the agent can drive IceBerg/AirBender/ShadowDragon/StickEm in one conversation.
"""
from __future__ import annotations

import json
from typing import Optional

from rich.console import Console

from ..modules.base import TOOL_REGISTRY, Tool
from .llm import AgentResponse, LLMConfig, get_provider, chat_with_failover

DEFAULT_SYSTEM = (
    "You are cyberbot, an agentic assistant for a penetration-testing platform "
    "used for LEGAL security education and authorized assessments only. You help "
    "the operator plan and execute engagements by calling the available tools. "
    "Always think step by step, call one tool at a time when unsure, and keep "
    "actions within the operator's authorized scope. When you have enough "
    "information, give a concise, structured answer with findings and next steps."
)


def _project_search(query: str = ""):
    """Agent tool: search projects + saved chats by keyword."""
    from ..projects import search
    if not query.strip():
        return "query required"
    results = search(query)
    if not results:
        return f"no projects or chats found matching '{query}'"
    return "\n".join(
        f"- [{r['type']}] {r['name']}: {r.get('snippet','')[:80]} ({r.get('matched','')})"
        for r in results)


def _project_open(query: str = ""):
    """Agent tool: find a project by keyword and make it active."""
    from ..projects import find_and_open
    if not query.strip():
        return "query required"
    name = find_and_open(query)
    if name:
        return f"opened project '{name}'. New prompts will be saved there."
    return f"no project found matching '{query}'. Create one with project_create."


def _project_create(name: str = "", description: str = ""):
    """Agent tool: create a new project and make it active."""
    from ..projects import create
    if not name.strip():
        return "name required"
    create(name, description=description)
    return f"created and activated project '{name}'."


def _project_tools() -> list[Tool]:
    """Return project-management tools so the agent can manage projects."""
    return [
        Tool(name="project.search",
             description="Search saved projects and chat histories by keyword. Use when the user "
                         "mentions a topic that might be an existing project.",
             parameters={"type": "object", "properties": {"query": {"type": "string"}},
                         "required": ["query"]},
             fn=_project_search),
        Tool(name="project.open",
             description="Find a project by keyword and set it as active (so prompts get saved there).",
             parameters={"type": "object", "properties": {"query": {"type": "string"}},
                         "required": ["query"]},
             fn=_project_open),
        Tool(name="project.create",
             description="Create a new named project and make it active.",
             parameters={"type": "object",
                         "properties": {"name": {"type": "string"},
                                        "description": {"type": "string", "default": ""}},
                         "required": ["name"]},
             fn=_project_create),
    ]


def build_system_prompt(base: str = "") -> str:
    """Inject the learned operator profile (memory) into the system prompt."""
    try:
        from ..memory import context_block
        from ..projects import get_active, search as project_search
        prompt = (base or DEFAULT_SYSTEM) + context_block()
        from ..projects import context_block as project_context
        prompt += project_context()
        # Tell the agent about the active project and that it can auto-switch.
        active = get_active()
        if active:
            prompt += f"\n\nActive project: '{active}'. Prompts are being saved there."
        prompt += (
            "\n\n## You choose the attack vector\n"
            "When the user describes a goal (e.g. 'check if my router is vulnerable' or "
            "'scan that server'), DO NOT ask them which tool to use. Pick the best tool "
            "or chain pipeline yourself based on what they described. Run it. Explain "
            "the results in plain language.\n\n"
            "## You manage projects\n"
            "If the user mentions a topic that matches an existing project (e.g. 'open "
            "my chicago work'), use the project_search tool to find it and auto-switch "
            "to it. If no project matches, create one automatically with a sensible name.\n"
            "You also have project_search, project_open, and project_create tools."
        )
        return prompt
    except Exception:
        return base or DEFAULT_SYSTEM


class Agent:
    def __init__(self, cfg: LLMConfig, registry=TOOL_REGISTRY, console: Optional[Console] = None):
        self.cfg = cfg
        self.provider = get_provider(cfg)
        self.registry = registry
        self.console = console or Console()
        system = build_system_prompt(cfg.system_prompt or DEFAULT_SYSTEM)
        self.messages: list[dict] = [{"role": "system", "content": system}]
        self.max_iterations = 12

    @property
    def tools(self) -> list[Tool]:
        return self.registry.all() + _project_tools()

    def _execute(self, call) -> str:
        tool = self.registry.get(call.name)
        if not tool:
            return f"ERROR: tool '{call.name}' not found."
        self.console.print(f"   [dim]calling[/dim] [cyan]{call.name}[/cyan]({call.arguments})")
        try:
            result = tool.fn(**call.arguments)
            # Record this action in memory for personalization across sessions.
            try:
                from ..memory import record
                record(platform=call.name.split(".")[0], action=call.name,
                       args=call.arguments, result_summary=str(result)[:300])
            except Exception:
                pass
            return str(result)
        except Exception as e:
            return f"ERROR executing {call.name}: {e}"

    def ask(self, prompt: str) -> str:
        """One user turn. Runs the tool loop until the LLM gives a final answer."""
        # Project selection can change between turns; refresh its scoped memory.
        self.messages[0]["content"] = build_system_prompt(self.cfg.system_prompt or DEFAULT_SYSTEM)
        self.messages.append({"role": "user", "content": prompt})

        for _ in range(self.max_iterations):
            resp: AgentResponse = chat_with_failover(
                self.provider, self.messages, self.tools, self.console)
            self.messages.append(self._assistant_msg(resp))

            if not resp.tool_calls:
                self.console.print()
                self.console.print(f"[green]cyberbot>[/green] {resp.text}")
                # Save to the active project if one is set.
                self._save_to_project(prompt, resp.text)
                return resp.text

            for call in resp.tool_calls:
                result = self._execute(call)
                self.messages.append({
                    "role": "tool",
                    "name": call.name,
                    "tool_call_id": call.id,
                    "content": result,
                })

        self.console.print("[yellow](reached max tool iterations)[/yellow]")
        return ""

    def _save_to_project(self, prompt: str, response: str) -> None:
        """Auto-save this prompt+response to the active project if one is set."""
        try:
            from ..projects import get_active, add_prompt
            active = get_active()
            if active:
                add_prompt(active, prompt, response, source="agent")
        except Exception:
            pass

    def _assistant_msg(self, resp: AgentResponse) -> dict:
        # Normalize for each provider. OpenAI/Ollama expect tool_calls list;
        # Anthropic expects content blocks. We keep a generic shape and let the
        # provider's chat() re-read its own raw if needed.
        msg = {"role": "assistant", "content": resp.text}
        if resp.tool_calls:
            msg["tool_calls"] = [
                {"id": c.id or f"call_{i}", "type": "function",
                 "function": {"name": c.name, "arguments": json.dumps(c.arguments)}}
                for i, c in enumerate(resp.tool_calls)
            ]
        return msg
