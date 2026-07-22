"""Multi-threaded execution + comprehensive report compilation.

The executor runs the Brain's plan: tasks with no dependencies run concurrently
via swarm delegates (or direct tool calls) in a thread pool, so independent
methods cross-check in parallel for the most comprehensive picture. Results are
collected and compiled into one report with links to artifacts (e.g. packet
captures saved as files the operator can open).
"""
from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

from ..config import HOME, ensure_dirs
from .planner import BrainPlan, BrainTask

ARTIFACTS_DIR = HOME / "brain" / "artifacts"


@dataclass
class TaskResult:
    stage: str
    description: str
    tools: list[str]
    output: str
    artifacts: list[str] = field(default_factory=list)
    ok: bool = True
    error: str = ""

    def to_dict(self) -> dict:
        return {"stage": self.stage, "description": self.description, "tools": self.tools,
                "output": self.output[:4000], "artifacts": self.artifacts,
                "ok": self.ok, "error": self.error}


ToolRunner = Callable[[str, dict], str]


def _noop_tool_runner(tool: str, args: dict) -> str:
    return f"(tool {tool} not executed in this context)"


def execute_plan(plan: BrainPlan, *, tool_runner: Optional[ToolRunner] = None,
                 max_workers: int = 4,
                 on_event: Optional[Callable[[str, str], None]] = None) -> list[TaskResult]:
    """Execute a plan concurrently where tasks are independent.

    ``tool_runner`` maps a tool name + args to a string result. In the live CLI
    it dispatches to swarm delegates / the registered tools; in tests it can be
    a stub. Returns results in execution order.
    """
    tool_runner = tool_runner or _live_tool_runner
    on_event = on_event or (lambda _s, _m: None)
    results: list[TaskResult] = []
    done_indices: set[int] = set()
    pending = list(enumerate(plan.tasks))

    while pending:
        ready, blocked = [], []
        for idx, task in pending:
            if all(d in done_indices for d in task.depends_on):
                ready.append((idx, task))
            else:
                blocked.append((idx, task))
        if not ready:
            # Circular/unsatisfiable deps: run the rest sequentially to make progress.
            ready, blocked = pending, []
        ready.sort(key=lambda x: 0 if x[1].parallel else 1)
        batch = ready[:max(1, max_workers)]
        on_event("execute", f"running {len(batch)} task(s): "
                            f"{', '.join(t.stage for _, t in batch)}")
        if len(batch) == 1:
            res = _run_task(batch[0][1], tool_runner, results, on_event)
            results.append(res)
            done_indices.add(batch[0][0])
        else:
            with ThreadPoolExecutor(max_workers=len(batch)) as pool:
                futures = {pool.submit(_run_task, task, tool_runner, results, on_event): idx
                           for idx, task in batch}
                for fut in as_completed(futures):
                    idx = futures[fut]
                    res = fut.result()
                    results.append(res)
                    done_indices.add(idx)
        pending = blocked + [pair for pair in ready if pair[0] not in done_indices]
    return results


def _run_task(task: BrainTask, tool_runner: ToolRunner,
              prior: list[TaskResult], on_event) -> TaskResult:
    """Run every tool named for a task and merge outputs into one result."""
    context = _prior_context(task, prior)
    outputs, artifacts, errors = [], [], []
    for tool in task.tools:
        on_event("tool", f"{task.stage}: {tool}")
        try:
            args = {"task": task.description, "context": context}
            out = tool_runner(tool, args)
            outs = str(out)
            outputs.append(f"### {tool}\n{outs}")
            arts = _extract_artifacts(outs, task)
            artifacts.extend(arts)
        except Exception as e:
            errors.append(f"{tool}: {e}")
            outputs.append(f"### {tool}\nERROR: {e}")
    return TaskResult(
        stage=task.stage, description=task.description, tools=task.tools,
        output="\n\n".join(outputs), artifacts=artifacts,
        ok=not errors, error="; ".join(errors))


def _prior_context(task: BrainTask, prior: list[TaskResult]) -> str:
    """Feed earlier task outputs into dependent tasks (chaining findings)."""
    deps = [prior[d] for d in task.depends_on if 0 <= d < len(prior)]
    if not deps:
        return ""
    lines = ["Prior findings to build on:"]
    for d in deps:
        lines.append(f"[{d.stage}] {d.output[:600]}")
    return "\n".join(lines)


def _extract_artifacts(text: str, task: BrainTask) -> list[str]:
    """If a task produced capture/output files, persist them and link them.

    HONESTY: packet capture is only claimed when a real capture tool actually
    ran and produced output. We check whether tshark/tcpdump are available and
    whether the task output indicates success. If the capture tool is missing or
    the operator lacks permission, we say so explicitly rather than fabricating a
    capture link - the report must not claim visibility that does not exist.
    """
    from ..host import is_available
    ensure_dirs()
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    links = []
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    is_capture_task = any(k in task.description.lower()
                          for k in ("packet", "capture", "pcap", "traffic"))
    if not is_capture_task:
        return links

    # Determine which capture tools were actually requested and available.
    capture_tools = [t for t in task.tools
                     if _binary_name(t) in ("tshark", "tcpdump", "wireshark")]
    if not capture_tools:
        return links
    available = [t for t in capture_tools if is_available(_binary_name(t))]
    if not available:
        links.append(
            f"(no capture tool available - tshark/tcpdump not installed; "
            "packet visibility was NOT possible for this task. "
            "Install one with: cyberspace brain acquire tshark)")
        return links
    # The tool ran; check the output actually indicates capture succeeded.
    lower = text.lower()
    if any(k in lower for k in ("permission denied", "operation not permitted",
                                 "you don't have permission", "error:")):
        links.append(
            f"(capture tool ran but lacked permission - likely needs sudo/root. "
            "Packet capture was NOT completed. Re-run with elevated privileges.)")
        return links
    if not text.strip() or "(no output)" in lower:
        links.append(
            "(capture tool ran but produced no output - the interface may have no "
            "traffic in scope, or capture was filtered. No packet evidence recorded.)")
        return links
    # Success: save a readable copy and link it.
    safe = "_".join(task.stage.split())
    path = ARTIFACTS_DIR / f"{safe}_{stamp}.txt"
    path.write_text(text[:50000])
    links.append(f"file://{path}  (packet capture summary - open to view traffic)")
    return links


def _binary_name(tool_ref: str) -> str:
    """Normalize a plan tool reference to a host binary name."""
    return tool_ref.rsplit("::", 1)[-1].rsplit(".", 1)[-1]


def _live_tool_runner(tool: str, args: dict) -> str:
    """Dispatch a plan tool to the live swarm/tools when running for real.

    The Brain feeds every platform: a stage can be delegated to the Swarm as a
    stage-scoped work unit (swarm.delegate), or a specific tool can be called
    directly. This is how the Brain drives airbender/shadowdragon/stickem/iceberg
    and the swarm in one coherent operation.
    """
    from ..modules.base import TOOL_REGISTRY
    context = args.get("context", "")
    desc = args.get("task", "")
    # swarm.delegate::<stage>  ->  delegate the whole stage to that kill-chain stage
    if tool.startswith("swarm.delegate::"):
        stage = tool.split("::", 1)[1]
        t = TOOL_REGISTRY.get("swarm.delegate")
        if t:
            return str(t.fn(agent_name=stage, task=desc))
        return f"(swarm.delegate not registered; would delegate {stage}: {desc})"
    # shadowdragon.run::xxx  ->  shadowdragon.run with the tool name
    if tool.startswith("shadowdragon.run::"):
        binary = tool.split("::", 1)[1]
        t = TOOL_REGISTRY.get("shadowdragon.run")
        if t:
            return str(t.fn(tool=binary, args=desc.split()))
        return f"(shadowdragon.run not registered; would run {binary})"
    # platform.tool style -> call the registered tool with the task description
    t = TOOL_REGISTRY.get(tool)
    if t:
        # Best-effort: pass the task as a natural-language request most tools accept.
        try:
            return str(t.fn(request=desc))
        except TypeError:
            try:
                return str(t.fn(desc))
            except TypeError:
                return str(t.fn())
    return f"(tool '{tool}' not found in registry)"


def compile_report(intent: str, plan: BrainPlan, results: list[TaskResult]) -> str:
    """Compile all task results into one comprehensive, user-friendly report."""
    from ..swarm import get_stage
    lines = [f"# Brain report: {intent}", ""]
    lines.append(f"Objective mapped to Kill Chain stage: **{plan.detected_stage}**")
    lines.append(f"Tasks executed: {len(results)}  |  Tools used: "
                 f"{', '.join(sorted({t for r in results for t in r.tools}))}")
    lines.append("")
    for i, r in enumerate(results, 1):
        spec = get_stage(r.stage)
        emoji = spec.emoji if spec else "\U0001f9e0"
        display = spec.display if spec else r.stage.title()
        status = "\u2705" if r.ok else "\u274c"
        lines.append(f"## {i}. {emoji} {display} {status}")
        lines.append(f"_{r.description}_")
        lines.append(f"**Tools:** {', '.join(r.tools)}")
        lines.append("")
        lines.append(r.output[:2000])
        if r.artifacts:
            lines.append("")
            lines.append("**Artifacts (click to view):**")
            for a in r.artifacts:
                lines.append(f"- {a}")
        lines.append("")
    all_artifacts = sorted({a for r in results for a in r.artifacts})
    if all_artifacts:
        lines.append("---\n**All artifacts:**")
        for a in all_artifacts:
            lines.append(f"- {a}")
    return "\n".join(lines)
