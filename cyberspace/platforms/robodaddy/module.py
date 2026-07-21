"""RoboDaddy module - dataset recommendations and model-training job orchestration.

A platform module that plugs RoboDaddy into the cyberspace system: it gets its
own CLI subcommand (`cyberspace robodaddy ...`) and registers agent tools so
cyberbot can drive planning, dry-runs, Vast.ai dispatch, and local serving.
"""
from __future__ import annotations

import typer
from rich.console import Console

from ...modules.base import Module, ModuleInfo, Tool, ToolRegistry

console = Console()


def _format_dataset_recommendations(rec: dict) -> str:
    lines = [
        f"matched use case: {rec['label']} ({rec['use_case']})",
        f"recommended base={rec['base_model']} method={rec['method']}",
        "datasets:",
    ]
    for idx, d in enumerate(rec["datasets"]):
        marker = "recommended" if idx == 0 else "candidate"
        lines.append(
            f"- {marker}: {d['name']} ({d['id']}), size={d['size']}, "
            f"license={d['license']}, access={d.get('access', 'unknown')}, "
            f"schema={d.get('schema', 'unknown')}; {d['note']}"
        )
    return "\n".join(lines)


def _split_cases(use_case: str = "general", use_cases: str = "") -> list[str]:
    raw = use_cases or use_case
    parts = [p.strip() for p in raw.replace("\n", ",").split(",")]
    return [p for p in parts if p] or ["general"]


def _tool_datasets(request: str = "", use_case: str = "", limit: int = 5):
    """Agent-callable: recommend datasets for a requested model.

    With a free-text `request`, searches across ALL datasets by relevance.
    With an explicit `use_case`, returns the curated recommendation.
    """
    if use_case:
        from .datasets import recommend_datasets
        rec = recommend_datasets(request, use_case=use_case, limit=limit)
        return _format_dataset_recommendations(rec)
    # Free-text fuzzy search across every dataset.
    from .datasets import search_datasets
    results = search_datasets(request, limit=limit or 10)
    if not results:
        return f"no datasets found matching '{request}'."
    lines = [f"search '{request}' -> {len(results)} dataset(s)", "datasets:"]
    for d in results:
        lines.append(
            f"- {d['name']} ({d['id']}), use_case={d.get('use_case', '?')}, "
            f"size={d['size']}, license={d['license']}, access={d.get('access', '?')}; {d['note']}"
        )
    return "\n".join(lines)


def _tool_plan(use_case: str = "general", days: int = 1):
    """Agent-callable: build a training plan + cost estimate."""
    from .datasets import recommend_datasets
    from .plan import build_plan
    p = build_plan(use_case, days=days)
    rec = recommend_datasets(use_case, use_case=p.use_case, limit=3)
    return (f"plan {p.name}: base={p.base_model} data={p.dataset_id} "
            f"gpu={p.num_gpus}x{p.gpu} epochs={p.epochs} time={p.hours}h "
            f"cost=${p.cost_low:.2f}-${p.cost_high:.2f}\n"
            f"{_format_dataset_recommendations(rec)}")


def _tool_train(use_case: str = "general", days: int = 1, base: str = "",
                gpu: str = "", dataset: str = "", use_cases: str = ""):
    """Agent-callable: run one or more training jobs (dry-run by default)."""
    from .plan import build_plan
    cases = _split_cases(use_case, use_cases)
    plans = [
        build_plan(case, base_model=(base or None), dataset_id=(dataset or None),
                   gpu=(gpu or None), days=days)
        for case in cases
    ]
    from .jobs import launch_background
    models = [launch_background(plan, dry_run=True) for plan in plans]
    return "\n".join(
        f"launched {m.name}: status={m.status} pid={m.stats.get('pid')} "
        f"log={m.stats.get('log_file')}; terminal may close"
        for m in models
    )


def _tool_models(**_):
    """Agent-callable: list trained models."""
    from .registry import list_models
    ms = list_models()
    if not ms:
        return "no models trained yet."
    return "\n".join(f"- {m.name}: {m.status} ({m.base_model})" for m in ms)


def _tool_jobs(**_):
    from .jobs import refresh_jobs
    models = refresh_jobs()
    if not models:
        return "no training jobs yet"
    return "\n".join(f"- {m.name}: {m.status}, provider={m.stats.get('provider', '-')}, "
                     f"cost={m.stats.get('cost_mid', m.stats.get('estimated_cost', '-'))}, "
                     f"log={m.stats.get('progress_file', m.stats.get('log_file', '-'))}"
                     for m in models)


def _tool_discover(intent: str = "", limit: int = 8):
    if not intent:
        return "intent required"
    from .discovery import discover_datasets, expand_search_terms, rank_datasets
    ranked = rank_datasets(intent, discover_datasets(intent, limit=min(limit * 2, 20),
                           search_terms=expand_search_terms(intent)), limit=limit)
    return "\n".join(f"- {d['id']}: {d.get('size')} {d.get('license')}/"
                     f"{d.get('access')} — {d.get('reason')}" for d in ranked)


def _tool_serve(model_name: str = ""):
    """Agent-callable: serve a model + issue API key."""
    if not model_name:
        return "model_name required"
    from .serve import serve as do_serve
    try:
        m, key = do_serve(model_name, target="ollama")
        return f"served {m.name} at {m.endpoint}, key={key[:16]}..."
    except ValueError as e:
        return str(e)


def _tool_connect(model_name: str = ""):
    if not model_name:
        return "model_name required"
    from .serve import use_as_cyberbot
    try:
        endpoint, _ = use_as_cyberbot(model_name)
        return f"connected {model_name} to Cyberspace Swarm at {endpoint}"
    except ValueError as exc:
        return str(exc)


def _tool_keys(action: str = "list", model_name: str = "", prefix: str = ""):
    from .registry import get_model, issue_key, list_keys, revoke_key
    if action == "list":
        keys = list_keys()
        return "\n".join(f"- {key.prefix}... model={key.model_name} id={key.key_id[:10]}"
                         for key in keys) or "no keys issued"
    if action == "new":
        model = get_model(model_name)
        if not model or model.status != "served" or not model.endpoint:
            return "model must be served before issuing a key"
        key = issue_key(model_name, model.endpoint, note="issued by Cyberspace AI")
        return f"created key {key.prefix}... in the native credential store; use CLI keys show to reveal it"
    if action == "revoke":
        return f"revoked {revoke_key(prefix)} key(s)"
    return "action must be list, new, or revoke"


def _coerce_known_agent(current, value: str):
    if isinstance(current, bool):
        return str(value).strip().lower() in ("1", "true", "yes", "y", "on")
    if isinstance(current, int):
        try:
            return int(value)
        except (TypeError, ValueError):
            return value
    if isinstance(current, float):
        try:
            return float(value)
        except (TypeError, ValueError):
            return value
    return value


def _coerce_for_agent(params, key: str, value: str):
    if "." in key:
        section, field_name = key.split(".", 1)
        container = getattr(params, section, None)
        if container is not None and field_name in container.__dict__:
            return _coerce_known_agent(getattr(container, field_name), value)
        return value
    if hasattr(params, key):
        return _coerce_known_agent(getattr(params, key), value)
    return value


def _tool_parameters(action: str = "show", key: str = "", value: str = "", profile: str = ""):
    """Agent-callable: view/set the full model-design parameter set."""
    from .parameters import (guide_text, PARAMETER_PROFILES, profile as load_profile,
                             load_parameters, save_parameters, merge_overrides, build_system_prompt)
    if action == "guide":
        return guide_text()
    if action == "profiles":
        return "\n".join(f"- {name}: {mp.label}" for name, mp in PARAMETER_PROFILES.items())
    if action == "set":
        current = load_profile(profile) if profile else (load_parameters() or load_profile("custom_blank"))
        if key:
            current = merge_overrides(current, **{key: _coerce_for_agent(current, key, value)})
        save_parameters(current)
        return (f"saved parameter profile ({current.label}). base={current.base_model or 'preset'} "
                f"method={current.method or 'preset'} epochs={current.epochs} datasets={current.dataset_ids}")
    current = load_parameters()
    if current is None:
        return ("no saved parameter profile. Start with: "
                "robodaddy.parameters action=set profile=cyber_redteam")
    return (f"profile: {current.label}\nbase_model={current.base_model} method={current.method}\n"
            f"focus={current.focus.to_dict()}\nguardrails={current.guardrails.to_dict()}\n"
            f"composed system prompt:\n{build_system_prompt(current)}")


def _tool_cyber(flavor: str = "redteam", use_case: str = "", dataset: str = "",
                days: int = 1, base: str = "", scope: str = "", guardrail_level: str = ""):
    """Agent-callable: build a cyber bot (red-team/adversary emulation or defense)."""
    from .parameters import profile as load_profile, merge_overrides, save_parameters
    from .plan import build_plan
    from .jobs import launch_background
    prof_name = "cyber_redteam" if str(flavor).startswith("red") else "cyber_defensive"
    params = load_profile(prof_name)
    overrides = {}
    if scope:
        overrides["guardrails.authorization_scope"] = scope
    if guardrail_level:
        overrides["guardrails.guardrail_level"] = guardrail_level
    if base:
        overrides["base_model"] = base
    if dataset:
        overrides["dataset_ids"] = [dataset]
    if overrides:
        params = merge_overrides(params, **overrides)
    save_parameters(params)
    uc = "cyber_redteam" if prof_name == "cyber_redteam" else "defensive_pentest"
    plan = build_plan(use_case or uc, parameters=params, days=days,
                      dataset_id=(params.dataset_ids[0] if params.dataset_ids else None))
    model = launch_background(plan, dry_run=True)
    return (f"cyber bot plan launched (dry-run): {model.name} status={model.status}. "
            f"base={plan.base_model} dataset={plan.dataset_id} "
            f"guardrail_level={params.guardrails.guardrail_level} "
            f"scope='{params.guardrails.authorization_scope}'.")


def _tool_custom(use_case: str = "general", dataset: str = "", base: str = "",
                 epochs=3, learning_rate=2e-4, batch_size=4, max_seq_len=2048,
                 lora_r=16, days: int = 1):
    """Agent-callable: build a fully custom bot with user-defined parameters."""
    from .parameters import profile as load_profile, save_parameters
    from .plan import build_plan
    from .jobs import launch_background
    params = load_profile("custom_blank")
    if base:
        params.base_model = base
    params.epochs = int(epochs)
    params.learning_rate = float(learning_rate)
    params.batch_size = int(batch_size)
    params.max_seq_len = int(max_seq_len)
    params.lora_r = int(lora_r)
    if dataset:
        params.dataset_ids = [dataset]
    save_parameters(params)
    plan = build_plan(use_case, parameters=params, days=days,
                      dataset_id=(params.dataset_ids[0] if params.dataset_ids else None))
    model = launch_background(plan, dry_run=True)
    return (f"custom bot plan launched (dry-run): {model.name} status={model.status}. "
            f"base={plan.base_model} dataset={plan.dataset_id} epochs={plan.epochs}.")


def _tool_refresh():
    """Agent-callable: refresh the most recent Hugging Face datasets into the cache."""
    from .refresh import refresh_datasets_cache, cache_info
    cached = refresh_datasets_cache()
    info = cache_info()
    return (f"refreshed {len(cached)} most recent datasets (cached {info.get('count', 0)}). "
            "View with robodaddy.latest.")


def _tool_latest(limit: int = 10):
    """Agent-callable: list the most recent cached Hugging Face datasets."""
    from .refresh import latest_datasets
    rows = latest_datasets(limit=limit or 10)
    if not rows:
        return ("no cached datasets yet. Run robodaddy.refresh to fetch the latest "
                "Hugging Face datasets.")
    return "\n".join(f"- {d['id']}: modified={d.get('last_modified','')} "
                     f"{d.get('license','?')}/{d.get('access','?')}; {d.get('note','')}"
                     for d in rows)


def _tool_recommend(intent: str = "", kind: str = "cyber", dataset: str = ""):
    """Agent-callable: AI-recommend the best parameters for an intent.

    Scans the option/config and returns recommended hyperparameters (with a
    deterministic fallback when no provider is configured).
    """
    from .parameters import profile as load_profile
    from .recommend import recommend_parameters
    from .refresh import latest_datasets
    prof_name = "cyber_redteam" if kind == "cyber" else "custom_blank"
    params = load_profile(prof_name)
    if dataset:
        params.dataset_ids = [dataset]
    latest = latest_datasets()
    rec = recommend_parameters(intent or "cyber red team", params, latest)
    return (f"recommended params ({rec.label}): base={rec.base_model or 'preset'} "
            f"method={rec.method} epochs={rec.epochs} lr={rec.learning_rate} "
            f"batch={rec.batch_size} seq_len={rec.max_seq_len} lora_r={rec.lora_r} "
            f"grad_accum={rec.gradient_accumulation_steps} optim={rec.optimizer} "
            f"sched={rec.lr_scheduler}. datasets={rec.dataset_ids}.")


class RoboDaddyModule(Module):
    def describe(self) -> ModuleInfo:
        return ModuleInfo(
            name="robodaddy", display_name="RoboDaddy", version="0.1.0",
            emoji="\U0001F916",  # robot
            description="Design and train your own open source model. Browse and pick any "
                        "Hugging Face dataset, set fully custom parameters (or use a cyber "
                        "red-team / adversary-emulation profile), set your own guardrails "
                        "before use, dispatch background QLoRA training, then serve it.",
            requires_tools=[],   # no host tools needed (everything is Python + remote APIs)
        )

    def register_tools(self, registry: ToolRegistry) -> None:
        registry.register(Tool(
            name="robodaddy.datasets",
            description="Search public training datasets by relevance to a free-text request "
                        "(e.g. 'python coding', 'blue team alerts'), or pass use_case for a curated "
                        "recommendation.",
            parameters={"type": "object",
                        "properties": {"request": {"type": "string", "default": ""},
                                       "use_case": {"type": "string", "default": ""},
                                       "limit": {"type": "integer", "default": 5}}},
            fn=_tool_datasets))
        registry.register(Tool(
            name="robodaddy.plan",
            description="Build a training plan with dataset options and cost/time estimate.",
            parameters={"type": "object",
                        "properties": {"use_case": {"type": "string"},
                                       "days": {"type": "integer", "default": 1}},
                        "required": ["use_case"]}, fn=_tool_plan))
        registry.register(Tool(
            name="robodaddy.train",
            description="Run one or more fine-tune jobs as dry-runs with progress files.",
            parameters={"type": "object",
                        "properties": {"use_case": {"type": "string"},
                                       "use_cases": {"type": "string", "default": "",
                                                     "description": "comma-separated model requests"},
                                       "days": {"type": "integer", "default": 1},
                                       "base": {"type": "string", "default": ""},
                                       "dataset": {"type": "string", "default": ""},
                                       "gpu": {"type": "string", "default": ""}},
                        "required": ["use_case"]}, fn=_tool_train))
        registry.register(Tool(
            name="robodaddy.models",
            description="List trained models in the registry.",
            parameters={"type": "object", "properties": {}}, fn=_tool_models))
        registry.register(Tool(
            name="robodaddy.jobs",
            description="Show background training jobs and whether each is queued, training, done, or failed.",
            parameters={"type": "object", "properties": {}}, fn=_tool_jobs))
        registry.register(Tool(
            name="robodaddy.discover",
            description="Search live Hugging Face datasets and use the configured provider to rank useful options.",
            parameters={"type": "object",
                        "properties": {"intent": {"type": "string"},
                                       "limit": {"type": "integer", "default": 8}},
                        "required": ["intent"]}, fn=_tool_discover))
        registry.register(Tool(
            name="robodaddy.serve",
            description="Write a local Ollama Modelfile and API-key record for a trained model.",
            parameters={"type": "object",
                        "properties": {"model_name": {"type": "string"}},
                        "required": ["model_name"]}, fn=_tool_serve))
        registry.register(Tool(
            name="robodaddy.connect",
            description="Connect a served RoboDaddy model as the active Cyberspace Swarm provider.",
            parameters={"type": "object",
                        "properties": {"model_name": {"type": "string"}},
                        "required": ["model_name"]}, fn=_tool_connect))
        registry.register(Tool(
            name="robodaddy.keys",
            description="List key prefixes, create a key for a served model, or revoke by prefix. Secrets are never returned to AI.",
            parameters={"type": "object",
                        "properties": {"action": {"type": "string", "enum": ["list", "new", "revoke"]},
                                       "model_name": {"type": "string", "default": ""},
                                       "prefix": {"type": "string", "default": ""}},
                        "required": ["action"]}, fn=_tool_keys))
        registry.register(Tool(
            name="robodaddy.parameters",
            description="View, set, or list the full model-design parameter set: training "
                        "hyperparameters, cyber capability focus, and the guardrails applied "
                        "before use. Nothing is limited - the user designs it. action = "
                        "show | guide | profiles | set (pass key/value, optional profile).",
            parameters={"type": "object",
                        "properties": {"action": {"type": "string", "default": "show",
                                                   "enum": ["show", "guide", "profiles", "set"]},
                                       "key": {"type": "string", "default": "",
                                               "description": "e.g. epochs or guardrails.guardrail_level"},
                                       "value": {"type": "string", "default": ""},
                                       "profile": {"type": "string", "default": "",
                                                   "description": "cyber_redteam | cyber_defensive | custom_blank"}},
                        "required": ["action"]}, fn=_tool_parameters))
        registry.register(Tool(
            name="robodaddy.cyber",
            description="Build a CYBER BOT for authorized red-team / adversary emulation or "
                        "defense. Attunes training to full offensive reasoning, adversary "
                        "modeling, and attack-path reasoning (footholds, exploitability, "
                        "finding chaining, full attack paths) using operator-inspired "
                        "multi-turn scenarios, with user-set guardrails. Launches a dry-run.",
            parameters={"type": "object",
                        "properties": {"flavor": {"type": "string", "default": "redteam",
                                                   "enum": ["redteam", "defensive"]},
                                       "use_case": {"type": "string", "default": ""},
                                       "dataset": {"type": "string", "default": ""},
                                       "scope": {"type": "string", "default": "",
                                                  "description": "authorized scope"},
                                       "guardrail_level": {"type": "string", "default": ""},
                                       "base": {"type": "string", "default": ""},
                                       "days": {"type": "integer", "default": 1}},
                        "required": ["flavor"]}, fn=_tool_cyber))
        registry.register(Tool(
            name="robodaddy.custom",
            description="Build a CUSTOM BOT with fully user-defined parameters and any "
                        "Hugging Face dataset - no limits. Launches a dry-run plan.",
            parameters={"type": "object",
                        "properties": {"use_case": {"type": "string", "default": "general"},
                                       "dataset": {"type": "string", "default": ""},
                                       "base": {"type": "string", "default": ""},
                                       "epochs": {"type": "integer", "default": 3},
                                       "learning_rate": {"type": "number", "default": 0.0002},
                                       "batch_size": {"type": "integer", "default": 4},
                                       "max_seq_len": {"type": "integer", "default": 2048},
                                       "lora_r": {"type": "integer", "default": 16},
                                       "days": {"type": "integer", "default": 1}},
                        "required": []}, fn=_tool_custom))
        registry.register(Tool(
            name="robodaddy.refresh",
            description="Refresh the most recent Hugging Face datasets into the local cache "
                        "so the user can view the latest data.",
            parameters={"type": "object", "properties": {}}, fn=_tool_refresh))
        registry.register(Tool(
            name="robodaddy.latest",
            description="List the most recent Hugging Face datasets from the local cache.",
            parameters={"type": "object",
                        "properties": {"limit": {"type": "integer", "default": 10}}},
            fn=_tool_latest))
        registry.register(Tool(
            name="robodaddy.recommend",
            description="AI-recommend the best parameters (hyperparameters, accumulation, "
                        "scheduler, optimizer, ...) for an intent. Scans the option/config "
                        "so the user does not have to read a guide. kind = cyber | custom.",
            parameters={"type": "object",
                        "properties": {"intent": {"type": "string", "default": ""},
                                       "kind": {"type": "string", "default": "cyber",
                                                 "enum": ["cyber", "custom"]},
                                       "dataset": {"type": "string", "default": ""}},
                        "required": ["intent"]}, fn=_tool_recommend))

    def build_cli(self) -> typer.Typer:
        from .cli import build_robodaddy_cli
        return build_robodaddy_cli(console)


MODULE = RoboDaddyModule()
