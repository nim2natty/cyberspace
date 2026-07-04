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
from .llm import AgentResponse, LLMConfig, get_provider

DEFAULT_SYSTEM = (
    "You are cyberbot, an agentic assistant for a penetration-testing platform "
    "used for LEGAL security education and authorized assessments only. You help "
    "the operator plan and execute engagements by calling the available tools. "
    "Always think step by step, call one tool at a time when unsure, and keep "
    "actions within the operator's authorized scope. When you have enough "
    "information, give a concise, structured answer with findings and next steps."
)


class Agent:
    def __init__(self, cfg: LLMConfig, registry=TOOL_REGISTRY, console: Optional[Console] = None):
        self.cfg = cfg
        self.provider = get_provider(cfg)
        self.registry = registry
        self.console = console or Console()
        system = cfg.system_prompt or DEFAULT_SYSTEM
        self.messages: list[dict] = [{"role": "system", "content": system}]
        self.max_iterations = 12

    @property
    def tools(self) -> list[Tool]:
        return self.registry.all()

    def _execute(self, call) -> str:
        tool = self.registry.get(call.name)
        if not tool:
            return f"ERROR: tool '{call.name}' not found."
        self.console.print(f"   [dim]calling[/dim] [cyan]{call.name}[/cyan]({call.arguments})")
        try:
            result = tool.fn(**call.arguments)
            return str(result)
        except Exception as e:
            return f"ERROR executing {call.name}: {e}"

    def ask(self, prompt: str) -> str:
        """One user turn. Runs the tool loop until the LLM gives a final answer."""
        self.messages.append({"role": "user", "content": prompt})

        for _ in range(self.max_iterations):
            resp: AgentResponse = self.provider.chat(self.messages, self.tools)
            self.messages.append(self._assistant_msg(resp))

            if not resp.tool_calls:
                self.console.print()
                self.console.print(f"[green]cyberbot>[/green] {resp.text}")
                return resp.text

            for call in resp.tool_calls:
                result = self._execute(call)
                self.messages.append({
                    "role": "tool",
                    "name": call.name,
                    "content": result,
                })

        self.console.print("[yellow](reached max tool iterations)[/yellow]")
        return ""

    def _assistant_msg(self, resp: AgentResponse) -> dict:
        # Normalize for each provider. OpenAI/Ollama expect tool_calls list;
        # Anthropic expects content blocks. We keep a generic shape and let the
        # provider's chat() re-read its own raw if needed.
        msg = {"role": "assistant", "content": resp.text}
        if resp.tool_calls:
            msg["tool_calls"] = [
                {"id": f"call_{i}", "type": "function",
                 "function": {"name": c.name, "arguments": json.dumps(c.arguments)}}
                for i, c in enumerate(resp.tool_calls)
            ]
        return msg
