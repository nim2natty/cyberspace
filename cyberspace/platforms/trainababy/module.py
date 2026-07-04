"""TrainABaby module - train your own personalized AI model, end to end.

A platform module that plugs TrainABaby into the cyberspace system: it gets its
own CLI subcommand (`cyberspace trainababy ...`) and registers agent tools so
cyberbot can drive training/serving in conversation.
"""
from __future__ import annotations

import typer
from rich.console import Console
from rich.table import Table

from ...modules.base import Module, ModuleInfo, Tool, ToolRegistry

console = Console()


def _tool_plan(use_case: str = "general", days: int = 1):
    """Agent-callable: build a training plan + cost estimate."""
    from .plan import build_plan
    p = build_plan(use_case, days=days)
    return (f"plan {p.name}: base={p.base_model} data={p.dataset_id} "
            f"gpu={p.num_gpus}x{p.gpu} epochs={p.epochs} time={p.hours}h "
            f"cost=${p.cost_low:.2f}-${p.cost_high:.2f}")


def _tool_train(use_case: str = "general", days: int = 1, base: str = "",
                gpu: str = ""):
    """Agent-callable: run a training job (dry-run by default)."""
    from .plan import build_plan
    from .train import run_training
    p = build_plan(use_case, base_model=(base or None), gpu=(gpu or None), days=days)
    m = run_training(p, dry_run=True)
    return (f"trained {m.name}: status={m.status} end_loss={m.stats.get('end_loss')} "
            f"samples={m.stats.get('samples_trained')}")


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


class TrainABabyModule(Module):
    def describe(self) -> ModuleInfo:
        return ModuleInfo(
            name="trainababy", display_name="TrainABaby", version="0.1.0",
            emoji="\U0001F476",  # 👶
            description="Train your own personalized AI model: datasets, cloud GPUs, API keys.",
            requires_tools=[],   # no host tools needed (everything is Python + remote APIs)
        )

    def register_tools(self, registry: ToolRegistry) -> None:
        registry.register(Tool(
            name="trainababy.plan",
            description="Build a training plan with cost/time estimate for a use case.",
            parameters={"type": "object",
                        "properties": {"use_case": {"type": "string"},
                                       "days": {"type": "integer", "default": 1}},
                        "required": ["use_case"]}, fn=_tool_plan))
        registry.register(Tool(
            name="trainababy.train",
            description="Run a fine-tune job (dry-run with simulated stats).",
            parameters={"type": "object",
                        "properties": {"use_case": {"type": "string"},
                                       "days": {"type": "integer", "default": 1},
                                       "base": {"type": "string", "default": ""},
                                       "gpu": {"type": "string", "default": ""}},
                        "required": ["use_case"]}, fn=_tool_train))
        registry.register(Tool(
            name="trainababy.models",
            description="List trained models in the registry.",
            parameters={"type": "object", "properties": {}}, fn=_tool_models))
        registry.register(Tool(
            name="trainababy.serve",
            description="Deploy a trained model behind an OpenAI-compatible endpoint + key.",
            parameters={"type": "object",
                        "properties": {"model_name": {"type": "string"}},
                        "required": ["model_name"]}, fn=_tool_serve))

    def build_cli(self) -> typer.Typer:
        from .cli import build_trainababy_cli
        return build_trainababy_cli(console)


MODULE = TrainABabyModule()
