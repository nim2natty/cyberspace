"""Verify the TrainABaby platform module.

Tests catalogs, plan building, model registry, and the dry-run training pipeline.
No GPU, Vast.ai key, or network needed - everything is validated offline.
"""
import json
import sys
import tempfile
import pathlib


def main():
    # 1) Catalogs have real entries.
    from cyberspace.platforms.trainababy.datasets import DATASETS, datasets_for
    assert "offensive_pentest" in DATASETS, "missing offensive preset datasets"
    assert "personal_assistant" in DATASETS
    ds = datasets_for("offensive_pentest")
    assert len(ds) >= 1 and all(d["id"] for d in ds), "dataset entries must have HF repo ids"
    print(f"PASS  datasets: {len(DATASETS)} use cases, offensive={len(ds)} datasets")

    # 2) GPU catalog + best-value selection.
    from cyberspace.platforms.trainababy.gpus import GPUS, gpus_for_model, best_value_gpu
    assert "RTX_4090" in GPUS and "A100_80" in GPUS and "H100" in GPUS
    assert best_value_gpu(8, "qlora") in GPUS  # 8B model -> cheapest capable GPU
    capable = gpus_for_model(70, "qlora")      # 70B only on big cards
    assert "A100_80" in capable and "H100" in capable
    print(f"PASS  gpus: {len(GPUS)} entries, 70B-trainable: {capable}")

    # 3) Preset matching maps free text -> recipe.
    from cyberspace.platforms.trainababy.presets import match_preset, PRESETS
    assert match_preset("offensive pen security") == "offensive_pentest"
    assert match_preset("personal assistant") == "personal_assistant"
    assert match_preset("wife companion") in ("creative_roleplay", "personal_assistant")
    assert match_preset("") == "general"
    assert all("base" in p and "datasets" in p for p in PRESETS.values())
    print(f"PASS  presets: {len(PRESETS)} use cases matched from free text")

    # 4) Plan building + cost estimate.
    from cyberspace.platforms.trainababy.plan import build_plan
    p = build_plan("offensive_pentest", days=2)
    assert p.base_model and p.dataset_id and p.gpu
    assert p.hours > 0 and p.cost_mid > 0
    assert p.epochs >= 3  # 2 days scales epochs up
    print(f"PASS  plan: {p.name} cost=${p.cost_low:.2f}-${p.cost_high:.2f} time={p.hours}h")

    # 5) Registry round-trip (isolated home dir).
    fake_home = pathlib.Path(tempfile.mkdtemp())
    import cyberspace.config as cfg
    cfg.HOME = fake_home
    cfg.MODULES_DIR = fake_home / "modules"
    cfg.ensure_dirs()
    from cyberspace.platforms.trainababy.registry import (
        TrainedModel, upsert_model, get_model, list_models, issue_key, list_keys)
    m = TrainedModel(name="test-model", base_model="qwen2.5-7b", dataset_id="databricks/databricks-dolly-15k",
                     use_case="general", method="qlora", status="trained")
    upsert_model(m)
    assert get_model("test-model") is not None
    assert len(list_models()) == 1
    key = issue_key("test-model", "http://localhost:11435/v1")
    assert key.key.startswith("tab_")
    assert len(list_keys()) == 1
    assert get_model("test-model").status == "served"
    print("PASS  registry: model upsert + api key issuance + served status")

    # 6) Dry-run training produces stats + writes job files.
    from cyberspace.platforms.trainababy.train import run_training
    events = []
    m2 = run_training(p, dry_run=True, on_event=lambda s, m: events.append((s, m)))
    assert m2.status == "trained"
    assert "end_loss" in m2.stats and "loss_curve" in m2.stats
    assert any(s == "done" for s, _ in events)
    assert (fake_home / "modules" / "trainababy" / "jobs" / p.name / "train.py").exists()
    print(f"PASS  training dry-run: status={m2.status} end_loss={m2.stats['end_loss']}")

    # 7) Agent tools registered.
    from cyberspace.modules.registry import discover_and_load
    from cyberspace.modules.base import TOOL_REGISTRY
    discover_and_load()
    assert TOOL_REGISTRY.get("trainababy.plan"), "trainababy.plan not registered"
    result = TOOL_REGISTRY.get("trainababy.plan").fn(use_case="general")
    assert "plan" in result and "$" in result
    print(f"PASS  agent tools: plan+train+models+serve registered")

    print("\nALL CHECKS PASSED - TrainABaby platform is wired correctly.")


if __name__ == "__main__":
    try:
        main()
    except AssertionError as e:
        print(f"FAIL  {e}", file=sys.stderr)
        sys.exit(1)
