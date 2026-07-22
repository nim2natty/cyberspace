"""The Cyberdeck orchestrator: plan -> acquire -> execute -> report -> learn.

It accepts a security objective, constructs a staged tool plan, resolves missing
dependencies, executes ready tasks concurrently, evaluates evidence, writes a
report, and records verified outcomes in the playbook.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional

from . import playbook
from .planner import plan as build_cyberdeck_plan
from .executor import execute_plan, compile_report, append_stage_criteria


def _on_noop(_s: str, _m: str) -> None:
    pass


@dataclass
class CyberdeckOutcome:
    intent: str
    report: str
    plan_summary: str
    success: bool
    tools_used: list


def run(intent: str, *, confirm_install: Optional[Callable] = None,
         tool_runner: Optional[Callable] = None, max_workers: int = 4,
         on_event: Optional[Callable[[str, str], None]] = None,
         learn: bool = True) -> CyberdeckOutcome:
    """Run the full Cyberdeck pipeline for an objective.

    Steps:
      1. Plan: decompose into multi-tool Kill Chain tasks.
      2. Acquire: find/install any missing software (confirmed).
      3. Execute: run tasks concurrently, chaining dependent findings.
      4. Report: compile an evidence report with artifact links.
      5. Learn: record success/failure in the playbook for next time.
    """
    on_event = on_event or _on_noop
    on_event("plan", "decomposing objective into a Kill Chain plan...")
    br_plan = build_cyberdeck_plan(intent)
    on_event("plan", f"{len(br_plan.tasks)} task(s) across stages: "
                      f"{', '.join(t.stage for t in br_plan.tasks)}")

    # Acquire missing tools.
    from .acquire import missing_tools, resolve_tools, install
    all_tools = [t for task in br_plan.tasks for t in task.tools]
    missing = missing_tools(all_tools)
    if missing:
        on_event("acquire", f"{len(missing)} tool(s) missing: {', '.join(missing)}")
        resolved = resolve_tools(missing, on_event=on_event)
        installed_any = False
        for name in missing:
            cand = resolved[name].get("candidate")
            if not cand:
                continue
            ok, msg = install(cand, confirm=confirm_install)
            if ok:
                installed_any = True
                on_event("acquire", f"installed {name}")
            else:
                on_event("acquire", f"could not install {name}: {msg}")
        if installed_any:
            # Re-resolve; newly installed tools are now usable.
            pass

    # Execute the plan.
    results = execute_plan(br_plan, tool_runner=tool_runner,
                           max_workers=max_workers, on_event=on_event)

    # Compile + assess. Overall success requires every task's per-tool criteria
    # to pass AND every stage's aggregate criteria to pass (measured against the
    # combined output of that stage, not each sub-task).
    plan_summary = f"{len(br_plan.tasks)} tasks, tools: {', '.join(all_tools)}"
    tasks_ok = all(r.ok for r in results) if results else False
    # Stage-level criteria against each stage's aggregated output.
    from .criteria import evaluate_stage, task_succeeded as _task_ok
    stage_notes = []
    stages_seen = []
    for r in results:
        if r.stage not in stages_seen:
            stages_seen.append(r.stage)
    stage_ok = True
    stage_evaluations = []
    for stage in stages_seen:
        combined = "\n\n".join(r.output for r in results if r.stage == stage)
        stage_results = evaluate_stage(stage, combined)
        ok, note = _task_ok(stage_results)
        stage_evaluations.append((stage, stage_results, ok, note))
        if not ok:
            stage_ok = False
            stage_notes.append(f"[{stage}] {note}")
        for sr in stage_results:
            on_event("criteria", f"[stage {stage}] {sr.criterion_id}: {sr.status} - {sr.reason}")
    success = tasks_ok and stage_ok
    report = append_stage_criteria(
        compile_report(intent, br_plan, results), stage_evaluations)
    tools_used = sorted({t for task in br_plan.tasks for t in task.tools})

    # Learn. Record per-task outcomes (criterion-based) so the playbook remembers
    # what actually achieved success, not merely what ran.
    if learn:
        by_index = {result.task_index: result for result in results}
        stage_passed = {stage: ok for stage, _results, ok, _note in stage_evaluations}
        for task_index, task in enumerate(br_plan.tasks):
            matching = by_index.get(task_index)
            outcome = ((matching.criteria_note or matching.output[:160])
                       if matching else "(no result)")
            playbook.record(playbook.PlaybookEntry(
                intent=intent, stage=task.stage, tools=task.tools,
                plan_summary=task.description, outcome=outcome,
                success=(matching.ok and stage_passed.get(task.stage, False)) if matching else False,
                artifacts=matching.artifacts if matching else []))
    if stage_notes:
        on_event("criteria", "stage criteria: " + " | ".join(stage_notes))
    on_event("done", "cyberdeck operation complete" if success else "cyberdeck operation finished with errors")
    return CyberdeckOutcome(intent=intent, report=report, plan_summary=plan_summary,
                        success=success, tools_used=tools_used)


def plan_only(intent: str) -> str:
    """Return a human-readable plan without executing (for the `cyberdeck plan` command)."""
    from .playbook import feed_forward_prompt
    p = build_cyberdeck_plan(intent)
    lines = [f"# Cyberdeck plan for: {intent}",
             f"Mapped to Kill Chain stage: {p.detected_stage}", ""]
    for i, task in enumerate(p.tasks):
        deps = f" (after task{'s' if len(task.depends_on) != 1 else ''} " \
               f"{', '.join(str(d+1) for d in task.depends_on)})" if task.depends_on else ""
        run_mode = "parallel" if task.parallel else "sequential"
        lines.append(f"{i+1}. [{task.stage}] {task.description}{deps} ({run_mode})")
        lines.append(f"   tools: {', '.join(task.tools)}")
    ff = feed_forward_prompt(intent)
    if ff:
        lines.append("")
        lines.append(ff.strip())
    return "\n".join(lines)
