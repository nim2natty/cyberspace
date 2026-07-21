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
    lines = [f"search '{request}' -> {len(results)} dataset(s):"]
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
    if len(plans) == 1:
        from .train import run_training
        models = [run_training(plans[0], dry_run=True)]
    else:
        from .train import run_training_batch
        models = run_training_batch(plans, dry_run=True)
    return "\n".join(
        f"trained {m.name}: status={m.status} end_loss={m.stats.get('end_loss')} "
        f"samples={m.stats.get('samples_trained')} progress={m.stats.get('progress_file')}"
        for m in models
    )


def _tool_models(**_):
    """Agent-callable: list trained models."""
    from .registry import list_models
    ms = list_models()
    if not ms:
        return "no models trained yet."
    return "\n".join(f"- {m.name}: {m.status} ({m.base_model})" for m in ms)


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


class RoboDaddyModule(Module):
    def describe(self) -> ModuleInfo:
        return ModuleInfo(
            name="robodaddy", display_name="RoboDaddy", version="0.1.0",
            emoji="\U0001F916",  # robot
            description="Plan, dry-run, and dispatch QLoRA fine-tunes with dataset recommendations.",
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
            name="robodaddy.serve",
            description="Write a local Ollama Modelfile and API-key record for a trained model.",
            parameters={"type": "object",
                        "properties": {"model_name": {"type": "string"}},
                        "required": ["model_name"]}, fn=_tool_serve))

    def build_cli(self) -> typer.Typer:
        from .cli import build_robodaddy_cli
        return build_robodaddy_cli(console)


MODULE = RoboDaddyModule()
