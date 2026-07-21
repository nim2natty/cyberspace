"""Durable detached RoboDaddy worker lifecycle and job status reconciliation."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

from ...config import MODULES_DIR, ensure_dirs
from .plan import TrainingPlan
from .registry import TrainedModel, get_model, list_models, upsert_model

JOBS_DIR = MODULES_DIR / "robodaddy" / "jobs"


def launch_background(plan: TrainingPlan, *, dry_run: bool = True,
                      vast_offer_id: Optional[int] = None) -> TrainedModel:
    """Launch a worker independent of the terminal and return its queued record."""
    ensure_dirs()
    if get_model(plan.name) is not None:
        plan.name = f"{plan.name}-{datetime.now().strftime('%Y%m%d-%H%M%S-%f')[:19]}"
    jdir = JOBS_DIR / plan.name
    jdir.mkdir(parents=True, exist_ok=True)
    plan_file = jdir / "plan.json"
    plan_file.write_text(json.dumps(plan.to_dict(), indent=2))
    log_file = jdir / "worker.log"
    args = _worker_command(plan_file, dry_run=dry_run, vast_offer_id=vast_offer_id)
    record = get_model(plan.name) or TrainedModel(
        name=plan.name, base_model=plan.base_model, dataset_id=plan.dataset_id,
        use_case=plan.use_case, method=plan.method)
    record.status = "queued"
    record.created = datetime.now().isoformat()
    record.stats = {**record.stats, "provider": "dry-run" if dry_run else "vastai",
                    "job_dir": str(jdir), "log_file": str(log_file),
                    "plan_file": str(plan_file), "queued": record.created,
                    "estimated_hours": plan.hours, "estimated_cost": plan.cost_mid}
    upsert_model(record)

    out = log_file.open("ab")
    kwargs = {"stdin": subprocess.DEVNULL, "stdout": out, "stderr": subprocess.STDOUT,
              "close_fds": True}
    if os.name == "nt":
        kwargs["creationflags"] = (getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0) |
                                   getattr(subprocess, "DETACHED_PROCESS", 0))
    else:
        kwargs["start_new_session"] = True
    try:
        process = subprocess.Popen(args, **kwargs)
    except Exception as exc:
        out.close()
        record.status = "failed"
        record.stats["error"] = f"could not launch background worker: {exc}"
        record.stats["finished"] = datetime.now().isoformat()
        upsert_model(record)
        return record
    out.close()
    current = get_model(plan.name) or record
    if current.status in ("queued", "training"):
        current.stats["pid"] = process.pid
        upsert_model(current)
    return current


def run_worker(plan_file: Path, *, dry_run: bool = True,
               vast_offer_id: Optional[int] = None) -> int:
    """Worker entry point. Always records a terminal state on normal exceptions."""
    data = json.loads(plan_file.read_text())
    plan = TrainingPlan(**{k: data[k] for k in TrainingPlan.__dataclass_fields__ if k in data})
    try:
        from .train import run_training
        run_training(plan, dry_run=dry_run, vast_offer_id=vast_offer_id)
        return 0
    except BaseException as exc:
        record = get_model(plan.name) or TrainedModel(
            name=plan.name, base_model=plan.base_model, dataset_id=plan.dataset_id,
            use_case=plan.use_case, method=plan.method)
        record.status = "failed"
        record.stats = {**record.stats, "error": str(exc), "finished": datetime.now().isoformat()}
        upsert_model(record)
        return 1


def refresh_jobs() -> list[TrainedModel]:
    """Mark dead local workers failed; preserve remote Vast.ai training state."""
    refreshed = []
    for model in list_models():
        pid = model.stats.get("pid")
        cloud_dispatched = bool(model.stats.get("vast_instance_id"))
        if model.status in ("queued", "training") and pid and not cloud_dispatched and not _alive(int(pid)):
            stats_file = Path(model.stats.get("job_dir", "")) / "stats.json"
            if stats_file.exists():
                try:
                    stats = json.loads(stats_file.read_text())
                    model.stats = {**model.stats, **stats}
                    model.status = "trained"
                except Exception:
                    model.status = "failed"
            else:
                model.status = "failed"
                model.stats["error"] = "background worker exited before writing stats"
            upsert_model(model)
        refreshed.append(model)
    return refreshed


def _worker_command(plan_file: Path, *, dry_run: bool, vast_offer_id: Optional[int]) -> list[str]:
    # A frozen executable re-enters its normal CLI; source installs use -m.
    base = [sys.executable] if getattr(sys, "frozen", False) else [sys.executable, "-m", "cyberspace"]
    args = [*base, "robodaddy", "worker", str(plan_file)]
    if dry_run:
        args.append("--dry-run")
    elif vast_offer_id is not None:
        args.extend(["--offer", str(vast_offer_id)])
    return args


def _alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        if os.name == "nt":
            result = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/NH"],
                                    capture_output=True, text=True, timeout=5)
            return str(pid) in result.stdout
        os.kill(pid, 0)
        return True
    except (OSError, subprocess.SubprocessError):
        return False