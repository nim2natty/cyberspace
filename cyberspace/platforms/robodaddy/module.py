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


class RoboDaddyModule(Module):
    def describe(self) -> ModuleInfo:
        return ModuleInfo(
            name="robodaddy", display_name="RoboDaddy", version="0.1.0",
            emoji="\U0001F916",  # robot
            description="Guided live data discovery, GPU pricing, background training, serving, and keys.",
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

    def build_cli(self) -> typer.Typer:
        from .cli import build_robodaddy_cli
        return build_robodaddy_cli(console)


MODULE = RoboDaddyModule()
