"""Schema-aware compilation of natural-language objectives into tool calls."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from .modules.base import Tool


class ToolArgumentError(ValueError):
    """A tool call could not be made precise enough to execute safely."""


@dataclass(frozen=True)
class CompiledToolCall:
    tool: str
    platform: str
    stage: str
    arguments: dict[str, Any]

    def preview(self) -> str:
        return (f"category={self.platform}/{self.stage} tool={self.tool} "
                f"arguments={json.dumps(self.arguments, sort_keys=True, default=str)}")


_URL = re.compile(r"https?://[^\s]+", re.I)
_CIDR_OR_IP = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}(?:/\d{1,2})?\b")
_DOMAIN = re.compile(r"\b(?:[a-zA-Z0-9-]+\.)+[a-zA-Z]{2,}\b")
_PATH = re.compile(r"(?:^|\s)(/[\w./~-]+|[A-Za-z]:\\[^\s]+)")


def compile_tool_call(tool: Tool, arguments: dict | None, prompt: str = "") -> CompiledToolCall:
    """Validate/coerce an AI tool call and infer only unambiguous missing fields."""
    schema = tool.parameters or {"type": "object", "properties": {}}
    properties = schema.get("properties", {})
    supplied = dict(arguments or {})
    unknown = sorted(set(supplied) - set(properties))
    if unknown:
        raise ToolArgumentError(
            f"{tool.name} received unsupported argument(s): {', '.join(unknown)}; "
            f"allowed: {', '.join(properties) or '(none)'}")

    values: dict[str, Any] = {}
    for name, spec in properties.items():
        if name in supplied and supplied[name] not in (None, ""):
            values[name] = _coerce(name, supplied[name], spec)
        elif name in schema.get("required", []):
            inferred = _infer(name, prompt, spec)
            if inferred is None:
                raise ToolArgumentError(
                    f"{tool.name} requires '{name}'. Provide it explicitly; the request "
                    "did not contain an unambiguous value.")
            values[name] = _coerce(name, inferred, spec)
        elif "default" in spec:
            values[name] = _coerce(name, spec["default"], spec)

    platform = tool.module or tool.name.partition(".")[0]
    stage = _tool_stage(tool.name)
    return CompiledToolCall(tool.name, platform, stage, values)


def _coerce(name: str, value: Any, spec: dict) -> Any:
    kind = spec.get("type", "string")
    try:
        if kind == "integer":
            value = int(value)
        elif kind == "number":
            value = float(value)
        elif kind == "boolean":
            if isinstance(value, str):
                low = value.strip().lower()
                if low not in ("true", "false", "yes", "no", "1", "0"):
                    raise ValueError
                value = low in ("true", "yes", "1")
            else:
                value = bool(value)
        elif kind == "array":
            if isinstance(value, str):
                value = [part.strip() for part in re.split(r"[;,\n]", value) if part.strip()]
            elif not isinstance(value, list):
                value = list(value)
        else:
            value = str(value).strip()
    except (TypeError, ValueError):
        raise ToolArgumentError(f"argument '{name}' must be {kind}") from None
    if "enum" in spec and value not in spec["enum"]:
        raise ToolArgumentError(
            f"argument '{name}' must be one of: {', '.join(map(str, spec['enum']))}")
    return value


def _infer(name: str, prompt: str, spec: dict) -> Any | None:
    text = (prompt or "").strip()
    if not text:
        return None
    url = _first(_URL, text)
    address = _first(_CIDR_OR_IP, text)
    domain = _first(_DOMAIN, text)
    if name == "url":
        return url
    if name == "domain":
        return domain
    if name in ("target", "lhost"):
        return address or url or domain
    if name in ("query", "intent", "request", "use_case"):
        return text
    if name == "success_criteria":
        return None
    if name in ("hashfile", "dataset"):
        match = _PATH.search(text)
        return match.group(1) if match else None
    if name == "hash":
        match = re.search(r"\b[a-fA-F0-9]{32,128}\b", text)
        return match.group(0) if match else None
    if name in ("ssid", "profile", "model_name", "tool", "name", "module", "action", "flavor"):
        enum = spec.get("enum", [])
        for choice in enum:
            if re.search(r"(?<!\w)" + re.escape(str(choice)) + r"(?!\w)", text, re.I):
                return choice
        quoted = re.search(r"['\"]([^'\"]+)['\"]", text)
        return quoted.group(1) if quoted else None
    return None


def _first(pattern: re.Pattern, text: str) -> str | None:
    match = pattern.search(text)
    return match.group(0).rstrip(".,)") if match else None


def _tool_stage(name: str) -> str:
    module, _, action = name.partition(".")
    if module == "airbender":
        return "recon"
    if module == "shadowdragon":
        if action in ("searchsploit", "msf_search"):
            return "weapon"
        if action in ("sqlmap", "hydra", "john", "hashcat", "secretsdump", "msf_run"):
            return "exploit"
        return "recon"
    if module == "iceberg":
        return "delivery" if action in ("browse", "new_profile") else "c2"
    if module == "stickem":
        return "install"
    if module in ("robodaddy", "cyberdeck", "project"):
        return "objectives"
    if module == "swarm":
        return "objectives"
    return "recon"