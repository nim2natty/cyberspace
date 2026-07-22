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
    task_index: int
    stage: str
    description: str
    tools: list[str]
    output: str
    artifacts: list[str] = field(default_factory=list)
    ok: bool = True
    error: str = ""
    criteria: list = field(default_factory=list)   # list[CriterionResult]
    criteria_note: str = ""

    def to_dict(self) -> dict:
        return {"task_index": self.task_index, "stage": self.stage,
                "description": self.description, "tools": self.tools,
                "output": self.output[:4000], "artifacts": self.artifacts,
                "ok": self.ok, "error": self.error,
                "criteria": [c.to_dict() if hasattr(c, "to_dict") else c for c in self.criteria],
                "criteria_note": self.criteria_note}


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
            res = _run_task(batch[0][0], batch[0][1], tool_runner, results, on_event)
            results.append(res)
            done_indices.add(batch[0][0])
        else:
            with ThreadPoolExecutor(max_workers=len(batch)) as pool:
                futures = {pool.submit(_run_task, idx, task, tool_runner, results, on_event): idx
                           for idx, task in batch}
                for fut in as_completed(futures):
                    idx = futures[fut]
                    res = fut.result()
                    results.append(res)
                    done_indices.add(idx)
        pending = blocked + [pair for pair in ready if pair[0] not in done_indices]
    return results


def _run_task(task_index: int, task: BrainTask, tool_runner: ToolRunner,
              prior: list[TaskResult], on_event) -> TaskResult:
    """Run every tool named for a task and merge outputs into one result.

    Success is measured against criteria (not just 'ran without error'): after
    the tools run, the applicable per-tool and per-stage criteria are evaluated
    against the combined output. A task is only 'ok' if no criterion FAILED.
    """
    from . import criteria as crit_mod
    context = _prior_context(task, prior)
    outputs, artifacts, errors, crit_results = [], [], [], []
    for tool in task.tools:
        on_event("tool", f"{task.stage}: {tool}")
        try:
            args = {"task": task.description, "context": context}
            out = tool_runner(tool, args)
            outs = str(out)
            outputs.append(f"### {tool}\n{outs}")
            from ..success import assess_tool_output
            status, reason = assess_tool_output(outs)
            empirical = crit_mod.evaluate_tool(
                tool, outs, stage=task.stage, description=task.description)
            # Prefer tool-specific empirical graders. The generic runtime grader is
            # only decisive for hard errors or tools without a specific grader.
            if status == "fail" or not empirical:
                crit_results.append(crit_mod.CriterionResult(
                    f"{tool}.contract_evidence", status, reason, outs[:200]))
            crit_results.extend(empirical)
            arts = _extract_artifacts(outs, task, tool=tool)
            artifacts.extend(arts)
        except Exception as e:
            errors.append(f"{tool}: {e}")
            outputs.append(f"### {tool}\nERROR: {e}")
    output = "\n\n".join(outputs)
    # Evaluate success criteria (platform-wide). This is what makes the Brain
    # "remember and execute" real success rather than mere absence of errors.
    ok, note = crit_mod.task_succeeded(crit_results)
    # If a tool threw, that's also a failure regardless of criteria.
    if errors:
        ok = False
        note = ("; ".join(errors) + (" | criteria: " + note if crit_results else "")).strip()
    for r in crit_results:
        on_event("criteria", f"{r.criterion_id}: {r.status} - {r.reason}")
    return TaskResult(
        task_index=task_index, stage=task.stage, description=task.description, tools=task.tools,
        output=output, artifacts=artifacts, ok=ok, error="; ".join(errors),
        criteria=crit_results, criteria_note=note)


@dataclass
class _BareResult:
    """Minimal adapter so criteria checks see a result with .output + .stage."""
    output: str
    stage: str = ""


def _prior_context(task: BrainTask, prior: list[TaskResult]) -> str:
    """Feed earlier task outputs into dependent tasks (chaining findings)."""
    by_index = {result.task_index: result for result in prior}
    deps = [by_index[d] for d in task.depends_on if d in by_index]
    if not deps:
        return ""
    lines = ["Prior findings to build on:"]
    for d in deps:
        lines.append(f"[{d.stage}] {d.output[:600]}")
    return "\n".join(lines)


def _extract_artifacts(text: str, task: BrainTask, *, tool: str = "") -> list[str]:
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
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    is_capture_task = any(k in task.description.lower()
                          for k in ("packet", "capture", "pcap", "traffic"))
    if not is_capture_task:
        return links

    # Determine which capture tools were actually requested and available.
    considered_tools = [tool] if tool else task.tools
    capture_tools = [t for t in considered_tools
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
    tool_name = _binary_name(tool) if tool else "capture"
    path = ARTIFACTS_DIR / f"{safe}_{tool_name}_{stamp}.txt"
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
            criteria = args.get("success_criteria") or (
                "Return evidence for the task and label every result pass, fail, or uncertain.")
            try:
                return str(t.fn(agent_name=stage, task=desc, success_criteria=criteria))
            except TypeError as exc:
                # Backward compatibility for third-party delegates registered before
                # success_criteria became part of the contract.
                if "success_criteria" not in str(exc):
                    raise
                return str(t.fn(agent_name=stage, task=desc))
        return f"(swarm.delegate not registered; would delegate {stage}: {desc})"
    # shadowdragon.kali_run::xxx -> generic registered Kali runner.
    if tool.startswith("shadowdragon.kali_run::"):
        binary = tool.split("::", 1)[1]
        t = TOOL_REGISTRY.get("shadowdragon.kali_run")
        if t:
            return str(t.fn(name=binary, args=desc))
        return f"ERROR: shadowdragon.kali_run not registered; could not run {binary}"
    # brain.report is a deliberate internal compiler over prior evidence.
    if tool == "brain.report":
        if not context.strip():
            return "ERROR: brain.report requires prior findings"
        return f"# Compiled Brain report\n\n{context}\n\nRequested summary: {desc}"
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
        if r.criteria_note:
            lines.append(f"**Success criteria:** {r.criteria_note}")
        if r.criteria:
            for c in r.criteria:
                mark = {"pass": "✅", "fail": "❌"}.get(c.status, "❔")
                lines.append(f"  - {mark} `{c.status}` {c.criterion_id}: {c.reason}")
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


def append_stage_criteria(report: str, stage_evaluations: list[tuple]) -> str:
    """Attach aggregate stage verdicts so no success decision is invisible."""
    if not stage_evaluations:
        return report
    lines = [report, "", "# Aggregate stage success criteria", ""]
    for stage, results, ok, note in stage_evaluations:
        lines.append(f"## {stage}: {'✅ pass' if ok else '❌ not passed'}")
        lines.append(note)
        for result in results:
            mark = {"pass": "✅", "fail": "❌"}.get(result.status, "❔")
            lines.append(f"- {mark} `{result.status}` {result.criterion_id}: {result.reason}")
        lines.append("")
    return "\n".join(lines)
