"""cyberspace module system.

Every platform (IceBerg, AirBender, ShadowDragon, StickEm) is a Module
subclass that:
  - declares a typer sub-app (its own CLI commands)
  - registers TOOLS with the agent (functions the LLM can call)
  - reports which host tools it needs (so the installer can provision them)

The main CLI auto-discovers all installed modules, so third parties can ship
`cyberspace_module_*` packages and they plug in automatically.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Optional

import typer


@dataclass
class Tool:
    """An agent-callable function with a JSON schema description."""
    name: str
    description: str
    parameters: dict
    fn: Callable[..., Any]
    module: str = ""
    success_criteria: list[str] = field(default_factory=list)
    verification: str = ""

    def __post_init__(self) -> None:
        if not self.success_criteria or not self.verification:
            from ..success import contract_for_tool
            criteria, verification = contract_for_tool(self.name, self.description)
            self.success_criteria = self.success_criteria or criteria
            self.verification = self.verification or verification

    def provider_description(self) -> str:
        """Return the same success-aware description for every LLM provider."""
        from ..success import tool_contract_text
        description = self.description
        if self.success_criteria:
            description += "\n\n" + tool_contract_text(
                self.name, self.success_criteria, self.verification)
        return description

    def to_openai(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.provider_description(),
                "parameters": self.parameters,
            },
        }


class ToolRegistry:
    """Holds all tools registered by all modules. The agent reads from here."""

    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        if not tool.module:
            tool.module = tool.name.split(".")[0]
        if not tool.success_criteria or not tool.verification:
            from ..success import contract_for_tool
            criteria, verification = contract_for_tool(tool.name, tool.description)
            tool.success_criteria = tool.success_criteria or criteria
            tool.verification = tool.verification or verification
        self._tools[tool.name] = tool

    def get(self, name: str) -> Optional[Tool]:
        return self._tools.get(name)

    def all(self) -> list[Tool]:
        return list(self._tools.values())

    def by_module(self, module: str) -> list[Tool]:
        return [t for t in self._tools.values() if t.module == module]

    def scoped(self, module: str) -> "ToolRegistry":
        """Return an independent registry containing only one exact module."""
        scoped = ToolRegistry()
        for tool in self.by_module(module):
            scoped.register(tool)
        return scoped


@dataclass
class ModuleInfo:
    """Static descriptor returned by a module's describe()."""
    name: str
    display_name: str
    version: str
    description: str
    emoji: str
    requires_tools: list[str] = field(default_factory=list)


class Module:
    """Base class for a cyberspace platform module.

    Subclasses override describe(), build_cli(), and register_tools().
    """

    def describe(self) -> "ModuleInfo":
        raise NotImplementedError

    def build_cli(self) -> typer.Typer:
        raise NotImplementedError

    def register_tools(self, registry: ToolRegistry) -> None:
        return None


# Global singletons the CLI + agent share.
TOOL_REGISTRY = ToolRegistry()
LOADED_MODULES: dict[str, Module] = {}
