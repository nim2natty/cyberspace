"""AI-assisted parameter recommendation and enhancement for RoboDaddy.

Two AI steps power the guided ``start`` flow:

1. :func:`recommend_parameters` - the configured Cyberspace provider scans the
   user's option/config (intent, cyber-vs-custom, chosen datasets, base model,
   guardrails) and recommends the *best* set of parameters: hyperparameters,
   gradient accumulation, scheduler, optimizer, etc. The user does not have to
   read a guide. Deterministic heuristic fallback when no provider/network.

2. :func:`enhance_parameters` - after the user finalizes their system prompt,
   the provider pulls similar/effective parameters to raise accuracy for that
   prompt algorithmically (e.g. longer seq_len for multi-turn attack paths,
   higher lora_r for richer tradecraft, warmup/scheduler tuned to the task).
"""
from __future__ import annotations

import json
from typing import Optional

from .parameters import ModelParameters, merge_overrides
from .presets import BASE_MODELS


def _provider():
    """Return (provider, cfg) or (None, None) when not configured."""
    try:
        from ...agent.config import load_config
        from ...agent.llm import get_provider
        cfg = load_config()
        if not cfg:
            return None, None
        return get_provider(cfg), cfg
    except Exception:
        return None, None


def _parse_json(text: str):
    t = (text or "").strip().removeprefix("```json").removesuffix("```").strip()
    start, end = t.find("{"), t.rfind("}")
    if start >= 0 and end > start:
        t = t[start:end + 1]
    return json.loads(t)


def _summarize_params(params: ModelParameters) -> dict:
    return {
        "label": params.label,
        "base_model": params.base_model,
        "method": params.method,
        "epochs": params.epochs,
        "learning_rate": params.learning_rate,
        "batch_size": params.batch_size,
        "max_seq_len": params.max_seq_len,
        "lora_r": params.lora_r,
        "gradient_accumulation_steps": params.gradient_accumulation_steps,
        "lr_scheduler": params.lr_scheduler,
        "optimizer": params.optimizer,
        "warmup_ratio": params.warmup_ratio,
        "weight_decay": params.weight_decay,
        "dataset_ids": params.dataset_ids,
        "focus": params.focus.to_dict(),
        "guardrails": params.guardrails.to_dict(),
    }


def recommend_parameters(intent, params, datasets, *, model_size_b=None):
    """Use the configured provider to recommend the best parameters for the config.

    Returns a *new* ModelParameters with recommended values applied. Falls back
    to a deterministic heuristic when no provider is configured or the call fails.
    """
    provider, _ = _provider()
    if provider is not None:
        try:
            ds_view = [{"id": d.get("id"), "schema": d.get("schema"),
                        "size": d.get("size"), "note": (d.get("note") or "")[:120]}
                       for d in datasets[:12]]
            schema_keys = list(BASE_MODELS.keys())
            parts = [
                "You tune LLM fine-tuning parameters. Read the user's training intent, ",
                "their current option/config, and candidate datasets, then recommend the ",
                "BEST parameters. Choose from the listed base models only. Return ONLY JSON ",
                "with these keys: base_model, method (qlora|lora|full), epochs, learning_rate, ",
                "batch_size, max_seq_len, lora_r, gradient_accumulation_steps, lr_scheduler ",
                "(cosine|linear|constant|cosine_with_restarts), optimizer ",
                "(adamw_torch|paged_adamw_8bit|adafactor), warmup_ratio, weight_decay, ",
                "lora_alpha, packing (bool). Omit any key you do not change.",
                "",
                "Intent: " + str(intent),
                "Available base models: " + json.dumps(schema_keys),
                "Current config: " + json.dumps(_summarize_params(params)),
                "Candidate datasets: " + json.dumps(ds_view),
            ]
            prompt = "\n".join(parts)
            resp = provider.chat([
                {"role": "system", "content": "You return only JSON parameter recommendations."},
                {"role": "user", "content": prompt}], [])
            rec = _parse_json(resp.text)
            if isinstance(rec, dict) and rec:
                return _apply_recommendation(params, rec)
        except Exception:
            pass
    return heuristic_recommend(intent, params, model_size_b=model_size_b)


def _apply_recommendation(params, rec):
    """Apply an AI recommendation dict onto a copy of params, validating types."""
    scalar_keys = ("epochs", "learning_rate", "batch_size", "max_seq_len", "lora_r",
                   "gradient_accumulation_steps", "lr_scheduler", "optimizer",
                   "warmup_ratio", "weight_decay", "lora_alpha", "base_model", "method")
    overrides = {}
    for k in scalar_keys:
        if k in rec and rec[k] not in (None, ""):
            overrides[k] = rec[k]
    if "packing" in rec and rec["packing"] is not None:
        overrides["packing"] = bool(rec["packing"])
    if overrides.get("base_model") and overrides["base_model"] not in BASE_MODELS:
        overrides.pop("base_model", None)
    if overrides.get("method") and overrides["method"] not in ("qlora", "lora", "full"):
        overrides.pop("method", None)
    for numk in ("epochs", "batch_size", "max_seq_len", "lora_r",
                 "gradient_accumulation_steps", "lora_alpha"):
        if numk in overrides:
            try:
                overrides[numk] = int(overrides[numk])
            except (TypeError, ValueError):
                overrides.pop(numk, None)
    for numk in ("learning_rate", "warmup_ratio", "weight_decay"):
        if numk in overrides:
            try:
                overrides[numk] = float(overrides[numk])
            except (TypeError, ValueError):
                overrides.pop(numk, None)
    if not overrides:
        return params
    return merge_overrides(params, **overrides)


def heuristic_recommend(intent, params, *, model_size_b=None):
    """Deterministic best-guess parameters when no AI provider is available."""
    overrides = {}
    base = params.base_model or "qwen2.5-7b"
    b = model_size_b or BASE_MODELS.get(base, {}).get("billion", 7)
    multi_turn = any(tok in (intent or "").lower() for tok in (
        "cyber", "red team", "attack path", "multi-turn", "scenario", "adversary"))
    sensitive = bool(getattr(params.focus, "sensitive_content", False))
    overrides["max_seq_len"] = 4096 if (multi_turn or sensitive) else 2048
    overrides["lora_r"] = 32 if (multi_turn or b >= 13) else 16
    if b >= 30:
        overrides.update({"batch_size": 1, "gradient_accumulation_steps": 8})
    elif b >= 13:
        overrides.update({"batch_size": 2, "gradient_accumulation_steps": 4})
    else:
        overrides.update({"batch_size": 4, "gradient_accumulation_steps": 4})
    if not params.method:
        overrides["method"] = "full" if b <= 3 else "qlora"
    method_now = overrides.get("method", params.method)
    overrides["optimizer"] = "paged_adamw_8bit" if method_now == "qlora" else "adamw_torch"
    overrides["lr_scheduler"] = "cosine"
    overrides["warmup_ratio"] = 0.03
    overrides["weight_decay"] = 0.01
    overrides["learning_rate"] = 2e-4 if method_now == "qlora" else 1e-5
    overrides["epochs"] = params.epochs or (4 if multi_turn else 3)
    overrides["lora_alpha"] = overrides["lora_r"] * 2
    return merge_overrides(params, **overrides)


def enhance_parameters(params, system_prompt):
    """Pull similar/effective parameters from the user's system prompt.

    Returns (enhanced_params, list_of_changes). Uses the provider when available;
    otherwise applies deterministic prompt-keyword heuristics.
    """
    provider, _ = _provider()
    if provider is not None:
        try:
            parts = [
                "Given this finalized system prompt for a model being fine-tuned, recommend ",
                "parameter changes that would raise accuracy for it. For example: long ",
                "multi-turn attack-path reasoning benefits from a larger max_seq_len and ",
                "lora_r; broad knowledge tasks benefit from more epochs. Return ONLY JSON ",
                "mapping parameter names to recommended values, plus 'reasons': a list of ",
                "short strings. Omit parameters you would not change.",
                "",
                "Current params: " + json.dumps(_summarize_params(params)),
                "System prompt:",
                str(system_prompt)[:2000],
            ]
            resp = provider.chat([
                {"role": "system", "content": "You return only JSON parameter changes."},
                {"role": "user", "content": "\n".join(parts)}], [])
            data = _parse_json(resp.text)
            if isinstance(data, dict):
                reasons = list(data.get("reasons", []))
                rec = {k: v for k, v in data.items() if k != "reasons"}
                enhanced = _apply_recommendation(params, rec)
                return enhanced, [str(r) for r in reasons][:8]
        except Exception:
            pass
    return _heuristic_enhance(params, system_prompt)


def _heuristic_enhance(params, system_prompt):
    """Keyword-based enhancement fallback."""
    text = (system_prompt or "").lower()
    changes = []
    out = params
    if any(k in text for k in ("multi-turn", "attack path", "scenario", "chain findings")):
        if (params.max_seq_len or 0) < 4096:
            out = merge_overrides(out, max_seq_len=4096)
            changes.append("raised max_seq_len to 4096 for multi-turn attack-path reasoning")
        if (params.lora_r or 0) < 32:
            out = merge_overrides(out, lora_r=32, lora_alpha=64)
            changes.append("raised lora_r to 32 to capture richer tradecraft")
    if any(k in text for k in ("adversary", "tradecraft", "offensive reasoning")):
        if (params.epochs or 0) < 4:
            out = merge_overrides(out, epochs=4)
            changes.append("set epochs to 4 for deeper adversary behavior")
    if any(k in text for k in ("concise", "short answers", "fast")):
        out = merge_overrides(out, epochs=2)
        changes.append("reduced epochs to 2 for a concise, fast assistant")
    if not changes:
        changes.append("no changes recommended; current parameters suit the prompt")
    return out, changes
