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
    # User-designed parameters (see .parameters). system_prompt attunes training;
    # focus/guardrails describe how the model should behave once served.
    system_prompt: str = ""
    focus: dict = field(default_factory=dict)
    guardrails: dict = field(default_factory=dict)
    extra_hyperparams: dict = field(default_factory=dict)
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
               num_gpus: int = 1, epochs: int = 3,
               parameters: Optional["ModelParameters"] = None) -> TrainingPlan:
    """Construct a plan from a use case + overrides, with cost/time estimates.

    When ``parameters`` (a robodaddy.parameters.ModelParameters) is supplied, the
    user's designed parameters are overlaid: hyperparameters, training method, and
    a system prompt composed from the cyber focus + guardrails. This is how the
    training process gets attuned to the model the user designed.
    """
    use_case = resolve_use_case(use_case)
    preset = preset_for(use_case)

    # If the user designed parameters, those take priority (base model, dataset,
    # method, hyperparameters, and the composed system prompt).
    method = preset["method"]
    chosen_system_prompt = ""
    focus_dict: dict = {}
    guardrails_dict: dict = {}
    extra_hp: dict = {}
    if parameters is not None:
        from .parameters import build_system_prompt
        if parameters.base_model and parameters.base_model in BASE_MODELS:
            base = parameters.base_model
        else:
            base = base_model or preset["base"]
        if parameters.method in ("qlora", "lora", "full"):
            method = parameters.method
        if parameters.dataset_ids:
            ds = parameters.dataset_ids[0]
        elif dataset_id:
            ds = dataset_id
        else:
            ds = datasets_for(preset["datasets"])[0]["id"]
        chosen_system_prompt = build_system_prompt(parameters, preset_prompt=preset.get("system_prompt", ""))
        focus_dict = parameters.focus.to_dict()
        guardrails_dict = parameters.guardrails.to_dict()
        extra_hp = {
            k: v for k, v in {
                "lora_alpha": parameters.lora_alpha,
                "lora_dropout": parameters.lora_dropout,
                "weight_decay": parameters.weight_decay,
                "warmup_ratio": parameters.warmup_ratio,
                "gradient_accumulation_steps": parameters.gradient_accumulation_steps,
                "lr_scheduler": parameters.lr_scheduler,
                "optimizer": parameters.optimizer,
                "seed": parameters.seed,
                "packing": parameters.packing,
            }.items() if v is not None
        }
        if parameters.epochs is not None:
            epochs = parameters.epochs
        if parameters.learning_rate is not None:
            pass  # applied below via plan field
        if parameters.batch_size is not None:
            pass  # applied below via plan field
        if parameters.max_seq_len is not None:
            pass  # applied below via plan field
        if parameters.lora_r is not None:
            pass  # applied below via plan field
    else:
        base = base_model or preset["base"]
        ds = dataset_id or datasets_for(preset["datasets"])[0]["id"]

    if base not in BASE_MODELS:
        base = preset["base"]
    bparams = BASE_MODELS[base]["billion"]

    chosen_gpu = gpu or best_value_gpu(bparams, method)
    if chosen_gpu not in GPUS:                          # fall back if unsupported
        chosen_gpu = best_value_gpu(bparams, method) or "A100_40"

    # Apply user hyperparameter overrides (no artificial limits).
    learning_rate = 2e-4
    batch_size = 4
    max_seq_len = 2048
    lora_r = 16
    if parameters is not None:
        if parameters.learning_rate is not None:
            learning_rate = parameters.learning_rate
        if parameters.batch_size is not None:
            batch_size = parameters.batch_size
        if parameters.max_seq_len is not None:
            max_seq_len = parameters.max_seq_len
        if parameters.lora_r is not None:
            lora_r = parameters.lora_r

    samples = min(200000, max(5000, _dataset_size_hint(ds)))
    # Scale epochs up with the user's day budget (more days => more passes),
    # unless the user explicitly pinned epochs via parameters (then keep them).
    if not (parameters is not None and parameters.epochs is not None):
        epochs = max(1, epochs + (days - 1))
    epochs = max(1, epochs)

    hours = _hours_for(bparams, samples, epochs, max_seq_len, chosen_gpu, num_gpus)
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
    notes.append(f"{method} on {num_gpus}x {chosen_gpu} ({GPUS[chosen_gpu]['vram_gb']}GB VRAM)")
    if GPUS[chosen_gpu]["qlora_max_b"] < bparams and method == "qlora":
        notes.append(f"WARNING: {chosen_gpu} VRAM may be tight for {bparams}B QLoRA - "
                     f"consider {best_value_gpu(bparams,'qlora')}.")
    if days >= 3:
        notes.append("long run - watch for preempted spot instances; checkpoint often.")
    if chosen_system_prompt:
        notes.append(f"attuned system prompt ({len(chosen_system_prompt)} chars) "
                     "composed from cyber focus + user guardrails.")
        if focus_dict and focus_dict.get("sensitive_content"):
            notes.append("sensitive-content handling enabled within the user's guardrails.")

    return TrainingPlan(
        name=f"{_safe_name(base)}-{_safe_name(use_case)}-d{days}",
        use_case=use_case, base_model=base,
        dataset_id=ds, dataset_revision=dataset_revision or "main",
        method=method, gpu=chosen_gpu, num_gpus=num_gpus,
        epochs=epochs, learning_rate=learning_rate, batch_size=batch_size,
        max_seq_len=max_seq_len, lora_r=lora_r,
        days=days, samples=samples, hours=hours,
        cost_low=low, cost_mid=mid, cost_high=high, notes=notes,
        system_prompt=chosen_system_prompt, focus=focus_dict,
        guardrails=guardrails_dict, extra_hyperparams=extra_hp,
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
