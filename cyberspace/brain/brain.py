"""The Brain orchestrator: plan -> acquire -> execute -> report -> learn.

This is the flagship entry point. It takes a plain-language objective and runs
the full evolving pipeline, feeding every platform (swarm, airbender,
shadowdragon, stickem, iceberg) and recording the outcome so the instance learns.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional

from . import playbook
from .planner import plan as build_brain_plan
from .executor import execute_plan, compile_report


def _on_noop(_s: str, _m: str) -> None:
    pass


@dataclass
class BrainOutcome:
    intent: str
    report: str
    plan_summary: str
    success: bool
    tools_used: list


def run(intent: str, *, confirm_install: Optional[Callable] = None,
         tool_runner: Optional[Callable] = None, max_workers: int = 4,
         on_event: Optional[Callable[[str, str], None]] = None,
         learn: bool = True) -> BrainOutcome:
    """Run the full Brain pipeline for an objective.

    Steps:
      1. Plan: decompose into multi-tool Kill Chain tasks.
      2. Acquire: find/install any missing software (confirmed).
      3. Execute: run tasks concurrently, chaining dependent findings.
      4. Report: compile a comprehensive report with artifact links.
      5. Learn: record success/failure in the playbook for next time.
    """
    on_event = on_event or _on_noop
    on_event("plan", "decomposing objective into a Kill Chain plan...")
    br_plan = build_brain_plan(intent)
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

    # Compile + assess.
    report = compile_report(intent, br_plan, results)
    plan_summary = f"{len(br_plan.tasks)} tasks, tools: {', '.join(all_tools)}"
    success = all(r.ok for r in results) if results else False
    tools_used = sorted({t for task in br_plan.tasks for t in task.tools})

    # Learn.
    if learn:
        for task in br_plan.tasks:
            matching = [r for r in results if r.stage == task.stage]
            outcome = matching[0].output[:200] if matching else "(no result)"
            playbook.record(playbook.PlaybookEntry(
                intent=intent, stage=task.stage, tools=task.tools,
                plan_summary=task.description, outcome=outcome,
                success=matching[0].ok if matching else False,
                artifacts=matching[0].artifacts if matching else []))
    on_event("done", "brain operation complete" if success else "brain operation finished with errors")
    return BrainOutcome(intent=intent, report=report, plan_summary=plan_summary,
                        success=success, tools_used=tools_used)


def plan_only(intent: str) -> str:
    """Return a human-readable plan without executing (for the `brain plan` command)."""
    from .playbook import feed_forward_prompt
    p = build_brain_plan(intent)
    lines = [f"# Brain plan for: {intent}",
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
