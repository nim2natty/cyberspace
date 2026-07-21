"""Training plan + cost/time estimation for RoboDaddy.

A TrainingPlan bundles every decision needed to fine-tune: base model, dataset,
GPU, method, epochs, and derived cost/time estimates. This is what `robodaddy
plan` produces and `robodaddy train` consumes.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Optional

from .datasets import dataset_by_id, datasets_for
from .gpus import GPUS, estimate_cost, best_value_gpu
from .presets import BASE_MODELS, preset_for, resolve_use_case


@dataclass
class TrainingPlan:
    name: str
    use_case: str                       # preset key
    base_model: str                     # e.g. "llama3.1-8b"
    dataset_id: str                     # HF repo id
    dataset_revision: str = "main"       # pinned HF commit/revision from discovery
    method: str = "qlora"               # qlora | lora | full
    gpu: str = "RTX_4090"               # GPU id from gpus.GPUS
    num_gpus: int = 1
    epochs: int = 3
    learning_rate: float = 2e-4
    batch_size: int = 4
    max_seq_len: int = 2048
    lora_r: int = 16
    days: int = 1                       # user-chosen budget
    samples: int = 50000                # approx rows trained per epoch
    # derived (filled by estimate()):
    hours: float = 0.0
    cost_low: float = 0.0
    cost_mid: float = 0.0
    cost_high: float = 0.0
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


def _hours_for(model_b: int, samples: int, epochs: int, seq_len: int,
               gpu: str, num_gpus: int) -> float:
    """Rough training-time estimate. Very approximate (order-of-magnitude).

    Empirical rule of thumb: throughput ~ (base_TPS / model_b) * seq_factor.
    Calibrated so a 7B QLoRA on 1x4090 does ~50k 2k-token samples/epoch in ~6h.
    """
    base_tps = 36000.0                                  # tokens/sec reference
    seq_factor = 2048.0 / max(seq_len, 512)
    tps = (base_tps / max(model_b, 1)) * seq_factor * num_gpus * 0.9
    total_tokens = samples * epochs * seq_len
    hours = total_tokens / (tps * 3600.0)
    return round(max(hours, 0.5), 2)


def build_plan(use_case: str, *, base_model: Optional[str] = None,
               dataset_id: Optional[str] = None, gpu: Optional[str] = None,
               dataset_revision: str = "main", days: int = 1,
               num_gpus: int = 1, epochs: int = 3) -> TrainingPlan:
    """Construct a plan from a use case + overrides, with cost/time estimates."""
    use_case = resolve_use_case(use_case)
    preset = preset_for(use_case)
    base = base_model or preset["base"]
    if base not in BASE_MODELS:
        base = preset["base"]
    bparams = BASE_MODELS[base]["billion"]

    ds_list = datasets_for(preset["datasets"])
    ds = dataset_id or ds_list[0]["id"]

    chosen_gpu = gpu or best_value_gpu(bparams, preset["method"])
    if chosen_gpu not in GPUS:                          # fall back if unsupported
        chosen_gpu = best_value_gpu(bparams, preset["method"]) or "A100_40"

    samples = min(200000, max(5000, _dataset_size_hint(ds)))
    # Scale epochs up with the user's day budget (more days => more passes).
    epochs = max(1, epochs + (days - 1))

    hours = _hours_for(bparams, samples, epochs, 2048, chosen_gpu, num_gpus)
    low, mid, high = estimate_cost(chosen_gpu, hours)

    notes = []
    notes.append(f"base model {base} ({bparams}B params)")
    dataset_meta = dataset_by_id(ds)
    if dataset_meta:
        notes.append(
            f"dataset {ds} ({dataset_meta.get('schema', 'unknown')} schema, "
            f"{dataset_meta.get('license', 'unknown')} license, "
            f"{dataset_meta.get('access', 'unknown')} access)"
        )
        if dataset_meta.get("access") != "public":
            notes.append("dataset requires accepting Hugging Face terms and setting HF_TOKEN before a real run.")
    notes.append(f"{preset['method']} on {num_gpus}x {chosen_gpu} ({GPUS[chosen_gpu]['vram_gb']}GB VRAM)")
    if GPUS[chosen_gpu]["qlora_max_b"] < bparams and preset["method"] == "qlora":
        notes.append(f"WARNING: {chosen_gpu} VRAM may be tight for {bparams}B QLoRA - "
                     f"consider {best_value_gpu(bparams,'qlora')}.")
    if days >= 3:
        notes.append("long run - watch for preempted spot instances; checkpoint often.")

    return TrainingPlan(
        name=f"{_safe_name(base)}-{_safe_name(use_case)}-d{days}",
        use_case=use_case, base_model=base,
        dataset_id=ds, dataset_revision=dataset_revision or "main",
        method=preset["method"], gpu=chosen_gpu, num_gpus=num_gpus,
        epochs=epochs, days=days, samples=samples, hours=hours,
        cost_low=low, cost_mid=mid, cost_high=high, notes=notes,
    )


def _dataset_size_hint(dataset_id: str) -> int:
    """Approximate row count for a dataset repo id (heuristic from name)."""
    id_low = dataset_id.lower()
    if "ultrachat" in id_low or "openorca" in id_low or "openhermes" in id_low:
        return 200000
    if "magicoder" in id_low or "evol-instruct-code" in id_low:
        return 80000
    if "primus-reasoning" in id_low:
        return 5000
    if "primus-instruct" in id_low:
        return 5000
    if "alpaca" in id_low or "dolly" in id_low:
        return 52000
    if "platypus" in id_low:
        return 25000
    if "github-code" in id_low:
        return 100000
    return 50000


def _safe_name(value: str) -> str:
    keep = [c.lower() if c.isalnum() else "-" for c in value]
    name = "".join(keep).strip("-")
    while "--" in name:
        name = name.replace("--", "-")
    return name or "model"
