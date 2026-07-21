"""GPU catalog for RoboDaddy - rough capacity and planning prices.

The static price ranges are only for cost estimates. Use `robodaddy instances`
for live Vast.ai offers before spending money.
"""
from __future__ import annotations

# GPU class -> spec. qlora_max_b = largest model size (in billions of params) you
# can QLoRA-finetune comfortably on this card in 4-bit.
GPUS = {
    "RTX_3090": {"vram_gb": 24, "qlora_max_b": 13, "full_ft_max_b": 3,
                 "dph_low": 0.20, "dph_high": 0.45, "class": "consumer"},
    "RTX_4090": {"vram_gb": 24, "qlora_max_b": 13, "full_ft_max_b": 3,
                 "dph_low": 0.35, "dph_high": 0.75, "class": "consumer"},
    "A6000":    {"vram_gb": 48, "qlora_max_b": 30, "full_ft_max_b": 7,
                 "dph_low": 0.55, "dph_high": 0.90, "class": "workstation"},
    "L40S":     {"vram_gb": 48, "qlora_max_b": 30, "full_ft_max_b": 7,
                 "dph_low": 0.80, "dph_high": 1.30, "class": "datacenter"},
    "A100_40":  {"vram_gb": 40, "qlora_max_b": 20, "full_ft_max_b": 7,
                 "dph_low": 1.00, "dph_high": 1.70, "class": "datacenter"},
    "A100_80":  {"vram_gb": 80, "qlora_max_b": 70, "full_ft_max_b": 13,
                 "dph_low": 1.50, "dph_high": 2.80, "class": "datacenter"},
    "H100":     {"vram_gb": 80, "qlora_max_b": 70, "full_ft_max_b": 30,
                 "dph_low": 2.20, "dph_high": 4.50, "class": "datacenter"},
    "H200":     {"vram_gb": 141, "qlora_max_b": 120, "full_ft_max_b": 70,
                 "dph_low": 3.00, "dph_high": 6.00, "class": "datacenter"},
}

# Inference-only hardware (cannot train, can SERVE). LPU = Groq's Language
# Processing Unit - very fast token/s, but you upload a finished model, not train.
INFERENCE_ACCELERATORS = {
    "LPU_GROQ":   {"note": "Groq LPU - extreme inference throughput (train elsewhere).",
                   "vram_gb": 0, "serving": True},
    "A10G":       {"vram_gb": 24, "serving": True},
    "T4":         {"vram_gb": 16, "serving": True},
}


def gpus_for_model(model_billion_params: int, method: str = "qlora") -> list[str]:
    """Return GPU ids that can train a model of the given size with the method."""
    cap = "qlora_max_b" if method == "qlora" else "full_ft_max_b"
    return [g for g, s in GPUS.items() if s[cap] >= model_billion_params]


def estimate_cost(gpu_id: str, hours: float) -> tuple[float, float, float]:
    """Return (low, mid, high) $ cost estimate for hours on a GPU."""
    s = GPUS[gpu_id]
    mid = (s["dph_low"] + s["dph_high"]) / 2 * hours
    return (s["dph_low"] * hours, mid, s["dph_high"] * hours)


def best_value_gpu(model_billion_params: int, method: str = "qlora") -> str:
    """Cheapest-$/hr GPU that can still train this model size."""
    candidates = gpus_for_model(model_billion_params, method)
    if not candidates:
        return ""
    return min(candidates, key=lambda g: GPUS[g]["dph_low"])


def compare_gpus(model_billion_params: int, method: str, samples: int, epochs: int,
                 seq_len: int, num_gpus: int = 1) -> list[dict]:
    """Return a GPU comparison for a planned run: time + cost for every compatible GPU.

    Each row: {gpu, vram_gb, hours, cost_low, cost_mid, cost_high, dph_low, capable}.
    Used by the guided flow to show a time/cost table and auto-pick the best one.
    """
    # Local import to avoid a circular dependency (plan imports gpus).
    from .plan import _hours_for, estimate_cost
    rows = []
    for gid, spec in GPUS.items():
        cap = "qlora_max_b" if method == "qlora" else "full_ft_max_b"
        capable = spec[cap] >= model_billion_params
        if not capable:
            continue
        hours = _hours_for(model_billion_params, samples, epochs, seq_len, gid, num_gpus)
        low, mid, high = estimate_cost(gid, hours)
        rows.append({
            "gpu": gid, "vram_gb": spec["vram_gb"], "capable": capable,
            "hours": round(hours, 2), "cost_low": round(low, 2),
            "cost_mid": round(mid, 2), "cost_high": round(high, 2),
            "dph_low": spec["dph_low"], "class": spec["class"],
        })
    # Cheapest total cost first.
    rows.sort(key=lambda r: r["cost_mid"])
    return rows


def pick_best_gpu(model_billion_params: int, method: str, samples: int, epochs: int,
                  seq_len: int, num_gpus: int = 1) -> str:
    """Pick the best-value compatible GPU for a run (cheapest projected total)."""
    rows = compare_gpus(model_billion_params, method, samples, epochs, seq_len, num_gpus)
    return rows[0]["gpu"] if rows else ""
