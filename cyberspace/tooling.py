"""Schema-aware compilation of natural-language objectives into tool calls."""
from __future__ import annotations

import json
import re
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Any, Callable, Iterable

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


@dataclass(frozen=True)
class ToolExecution:
    command: CompiledToolCall
    status: str
    reason: str
    evidence: str
    elapsed: float
    success_criteria: tuple[str, ...]
    verification: str


BATCH_PLANNING_INSTRUCTIONS = """
## Fast command planning
For an actionable request, plan the complete bounded operation in ONE response. Return
all independent tool calls together (maximum 6), with exact schema-valid arguments.
Choose the smallest set of tools that answers the requested information; avoid duplicate,
exhaustive, or unrelated operations. Do not call one tool and wait before selecting the
rest. Cyberspace will show the command list, execute independent calls concurrently, and
grade their evidence against each tool's success contract. For a non-actionable question,
answer directly without a tool call.
""".strip()


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


def execute_tool_batch(calls: Iterable, tools: Iterable[Tool], prompt: str, *,
                       console=None, stage: str = "", max_workers: int = 6,
                       recorder: Callable | None = None) -> tuple[str, list[ToolExecution]]:
    """Compile an entire command list, run it concurrently, and grade real evidence."""
    tool_map = {tool.name: tool for tool in tools}
    calls = list(calls)
    if len(calls) > max_workers:
        return (f"# Command plan — FAIL\n\nNo commands executed: the model proposed "
                f"{len(calls)} commands; the bounded maximum is {max_workers}. Narrow the "
                "objective or select the smallest non-duplicate command set.", [])
    compiled: list[tuple[Any, Tool, CompiledToolCall]] = []
    errors = []
    for index, call in enumerate(calls, 1):
        tool = tool_map.get(call.name)
        if not tool:
            errors.append(f"{index}. {call.name}: tool is unavailable or outside this scope")
            continue
        try:
            command = compile_tool_call(tool, call.arguments, prompt)
            compiled.append((call, tool, command))
        except Exception as exc:
            errors.append(f"{index}. {call.name}: {exc}")
    if errors:
        report = ("# Command plan — FAIL\n\nNo commands executed because the plan was not "
                  "fully precise and in scope.\n" + "\n".join(f"- {error}" for error in errors))
        return report, []

    if console:
        console.print(f"\n[bold cyan]Command plan ({len(compiled)})[/bold cyan]")
        for index, (_, _, command) in enumerate(compiled, 1):
            console.print(f"  [cyan]{index}.[/cyan] {command.preview()}")

    def run_one(item):
        _call, tool, command = item
        started = time.perf_counter()
        try:
            output = str(tool.fn(**command.arguments))
        except Exception as exc:
            output = f"ERROR executing {tool.name}: {exc}"
        elapsed = time.perf_counter() - started
        status, reason = _grade_output(tool, output, stage or command.stage, prompt)
        if recorder:
            try:
                recorder(command, output)
            except Exception:
                pass
        return ToolExecution(command, status, reason, output, elapsed,
                             tuple(tool.success_criteria), tool.verification)

    batch_started = time.perf_counter()
    with ThreadPoolExecutor(max_workers=max(1, len(compiled))) as pool:
        futures = [pool.submit(run_one, item) for item in compiled]
        executions = [future.result() for future in futures]
    report = format_batch_report(
        executions, stage=stage, elapsed=time.perf_counter() - batch_started)
    return report, executions


def format_batch_report(executions: list[ToolExecution], *, stage: str = "",
                        elapsed: float = 0.0) -> str:
    statuses = [row.status for row in executions]
    stage_results = []
    if stage:
        try:
            from .cyberdeck.criteria import evaluate_stage
            stage_results = evaluate_stage(stage, "\n\n".join(row.evidence for row in executions))
        except Exception:
            stage_results = []
    statuses.extend(result.status for result in stage_results)
    overall = "FAIL" if "fail" in statuses else (
        "UNCERTAIN" if "uncertain" in statuses or not statuses else "PASS")
    lines = [f"# Command execution — {overall}", "",
             f"Commands executed: {len(executions)} concurrently in {elapsed:.2f}s", ""]
    for index, row in enumerate(executions, 1):
        mark = {"pass": "PASS", "fail": "FAIL"}.get(row.status, "UNCERTAIN")
        lines.extend([
            f"## {index}. {row.command.tool} — {mark} ({row.elapsed:.2f}s)",
            f"**Category:** {row.command.platform}/{row.command.stage}",
            f"**Arguments:** `{json.dumps(row.command.arguments, sort_keys=True, default=str)}`",
            "**Success criteria:** " + " | ".join(row.success_criteria),
            f"**Verification:** {row.verification}",
            f"**Verdict:** {row.reason}",
            "**Evidence:**",
            "```text", row.evidence[:3000] or "(no output)", "```", "",
        ])
    if stage_results:
        lines.extend([f"## Aggregate stage criterion: {stage}", ""])
        for result in stage_results:
            lines.append(
                f"- {result.status.upper()} `{result.criterion_id}`: {result.reason}")
    return "\n".join(lines).rstrip()


def _grade_output(tool: Tool, output: str, stage: str, prompt: str) -> tuple[str, str]:
    from .success import assess_tool_output
    runtime_status, runtime_reason = assess_tool_output(output)
    if runtime_status == "fail":
        return runtime_status, runtime_reason
    try:
        from .cyberdeck.criteria import evaluate_tool
        empirical = evaluate_tool(tool.name, output, stage=stage, description=prompt)
    except Exception:
        empirical = []
    if empirical:
        if any(result.status == "fail" for result in empirical):
            failed = [result.reason for result in empirical if result.status == "fail"]
            return "fail", "; ".join(failed)
        if any(result.status != "pass" for result in empirical):
            uncertain = [result.reason for result in empirical if result.status != "pass"]
            return "uncertain", "; ".join(uncertain)
        return "pass", "; ".join(result.reason for result in empirical)
    return runtime_status, runtime_reason


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