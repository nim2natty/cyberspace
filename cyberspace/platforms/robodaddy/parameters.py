"""Full tunable parameter set for RoboDaddy.

This module lets a user *design* the model they want to train with a complete,
explicit set of parameters, and helps them do so with a built-in guide. It covers
three things:

1. **Training hyperparameters** - epochs, learning rate, batch size, LoRA rank,
   scheduler, optimizer, max sequence length, warmup, weight decay, etc. Nothing
   here is artificially limited; the user can dial any value the underlying
   HF TRL / PEFT stack accepts.

2. **Cyber capability focus** - toggles that attune the training to a particular
   kind of cyber model: full offensive reasoning, realistic adversary modeling,
   attack-path reasoning (analyze footholds, explore exploitability, chain
   findings, reason through full attack paths), operator-inspired multi-turn
   scenarios, and the handling of sensitive security content. These flags shape
   the generated system prompt and the guidance text, so the resulting open
   source model is built for the job the user designed it for.

3. **User-set guardrails** - applied *before* the model is used. The user declares
   an authorization scope, picks a guardrail level, and lists allowed/denied
   categories. This is how an authorized red-team / adversary-emulation model is
   kept on its leash for autonomous operations and deep defensive workflows.

A hard safety floor is enforced regardless of configuration: a small set of
categories (notably the sexualization of minors and real-world harm to
non-consenting third parties) are always refused. Everything else is the user's
choice, for legal, authorized use.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from typing import Optional

from ...config import MODULES_DIR, ensure_dirs

PARAMS_FILE = MODULES_DIR / "robodaddy" / "parameters.json"

# Categories that are ALWAYS refused, no matter what the user configures.
# This is a non-negotiable safety floor baked into every generated system prompt.
_HARD_FLOOR = [
    "sexualization of minors (CSAM/CSEC)",
    "real-world harm to non-consenting people or systems",
    "weapons of mass destruction instructions",
]


@dataclass
class Guardrails:
    """User-set safety boundaries applied before the trained model is used."""
    authorization_confirmed: bool = False
    authorization_scope: str = "authorized lab / engagement only"
    guardrail_level: str = "authorized-lab"
    allowed_categories: list[str] = field(default_factory=lambda: [
        "reconnaissance", "vulnerability analysis", "exploit reasoning",
        "post-exploitation reasoning", "attack-path chaining", "reporting",
    ])
    denied_categories: list[str] = field(default_factory=list)
    refuse_outside_scope: bool = True

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class CyberFocus:
    """Toggles that attune training to a particular cyber model flavor."""
    offensive_reasoning: bool = True
    adversary_modeling: bool = True
    attack_path_reasoning: bool = True
    multi_turn_scenarios: bool = True
    sensitive_content: bool = True
    foothold_analysis: bool = True
    operator_tasks: bool = True
    real_attack_vectors: bool = True

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ModelParameters:
    """The complete set of parameters a user designs their model with."""
    base_model: str = ""
    system_prompt: str = ""
    success_criteria: list[str] = field(default_factory=list)
    method: str = ""
    epochs: Optional[int] = None
    learning_rate: Optional[float] = None
    batch_size: Optional[int] = None
    max_seq_len: Optional[int] = None
    lora_r: Optional[int] = None
    lora_alpha: Optional[int] = None
    lora_dropout: Optional[float] = None
    weight_decay: Optional[float] = None
    warmup_ratio: Optional[float] = None
    gradient_accumulation_steps: Optional[int] = None
    lr_scheduler: Optional[str] = None
    optimizer: Optional[str] = None
    seed: Optional[int] = None
    packing: Optional[bool] = None
    dataset_ids: list[str] = field(default_factory=list)
    focus: CyberFocus = field(default_factory=CyberFocus)
    guardrails: Guardrails = field(default_factory=Guardrails)
    label: str = "custom"

    def to_dict(self) -> dict:
        return asdict(self)


# ---------------------------------------------------------------------------
# Preset parameter profiles
# ---------------------------------------------------------------------------
def _focus(**kw) -> CyberFocus:
    base = CyberFocus().to_dict()
    base.update(kw)
    return CyberFocus(**base)


def _gr(**kw) -> Guardrails:
    base = Guardrails().to_dict()
    base.update(kw)
    return Guardrails(**base)


PARAMETER_PROFILES = {
    "cyber_redteam": ModelParameters(
        label="Cyber Bot - Red Team / Adversary Emulation",
        base_model="llama3.1-8b",
        method="qlora",
        epochs=4,
        learning_rate=2e-4,
        batch_size=4,
        max_seq_len=4096,
        lora_r=32,
        gradient_accumulation_steps=4,
        lr_scheduler="cosine",
        warmup_ratio=0.03,
        optimizer="paged_adamw_8bit",
        focus=_focus(
            offensive_reasoning=True, adversary_modeling=True,
            attack_path_reasoning=True, multi_turn_scenarios=True,
            sensitive_content=True, foothold_analysis=True,
            operator_tasks=True, real_attack_vectors=True,
        ),
        guardrails=_gr(
            guardrail_level="red-team-engagement",
            authorization_scope="declared, authorized engagement scope only",
            allowed_categories=[
                "reconnaissance", "vulnerability analysis", "exploit reasoning",
                "post-exploitation reasoning", "attack-path chaining",
                "lateral movement reasoning", "C2 tradecraft concepts",
                "reporting and detection recommendations",
            ],
        ),
    ),
    "cyber_defensive": ModelParameters(
        label="Cyber Bot - Defensive / Detection Engineering",
        base_model="qwen2.5-7b",
        method="qlora",
        epochs=3,
        focus=_focus(
            offensive_reasoning=False, adversary_modeling=True,
            attack_path_reasoning=True, multi_turn_scenarios=True,
            sensitive_content=False, foothold_analysis=True,
            operator_tasks=False, real_attack_vectors=True,
        ),
        guardrails=_gr(
            guardrail_level="research-only",
            authorization_scope="detection engineering and threat analysis",
            allowed_categories=[
                "log analysis", "detection rules", "threat intelligence",
                "attack-path analysis for defense", "triage and hardening",
            ],
        ),
    ),
    "custom_blank": ModelParameters(
        label="Custom Bot - Fully User-Defined",
    ),
}


def profile(name: str) -> ModelParameters:
    """Return a copy of a named parameter profile."""
    src = PARAMETER_PROFILES.get(name, PARAMETER_PROFILES["custom_blank"])
    d = src.to_dict()
    focus = CyberFocus(**d.pop("focus"))
    gr = Guardrails(**d.pop("guardrails"))
    return ModelParameters(focus=focus, guardrails=gr, **d)


# ---------------------------------------------------------------------------
# Persistence (saved user profile)
# ---------------------------------------------------------------------------
def save_parameters(params: ModelParameters) -> Path:
    """Persist the user's chosen parameter profile to disk."""
    ensure_dirs()
    PARAMS_FILE.parent.mkdir(parents=True, exist_ok=True)
    PARAMS_FILE.write_text(json.dumps(params.to_dict(), indent=2))
    return PARAMS_FILE


def load_parameters() -> Optional[ModelParameters]:
    """Load the saved user parameter profile, or None if not set."""
    if not PARAMS_FILE.exists():
        return None
    try:
        data = json.loads(PARAMS_FILE.read_text())
        focus = CyberFocus(**(data.get("focus") or {}))
        gr = Guardrails(**(data.get("guardrails") or {}))
        rest = {k: v for k, v in data.items() if k not in ("focus", "guardrails")}
        return ModelParameters(focus=focus, guardrails=gr, **rest)
    except Exception:
        return None


# ---------------------------------------------------------------------------
# System prompt composition - this attunes the training process
# ---------------------------------------------------------------------------
def build_system_prompt(params: ModelParameters, *, preset_prompt: str = "") -> str:
    """Compose the training system prompt from the cyber focus + guardrails."""
    if params.system_prompt.strip():
        prompt = params.system_prompt.strip() + "\n\n" + _floor_line()
        return _append_success_criteria(prompt, params.success_criteria)

    f = params.focus
    g = params.guardrails

    parts: list[str] = []
    parts.append(
        "You are a security reasoning assistant designed by RoboDaddy for "
        "authorized red-team operations, adversary emulation, and deep defensive "
        "workflows. You reason and advise; you do not execute attacks. You operate "
        "only within the operator's declared, authorized scope.")

    caps = []
    if f.offensive_reasoning:
        caps.append("full offensive reasoning across an assessment objective")
    if f.adversary_modeling:
        caps.append("realistic adversary modeling (TTPs, tradecraft, MITRE ATT&CK mapping)")
    if f.attack_path_reasoning:
        caps.append(
            "attack-path reasoning: analyze footholds, explore exploitability, "
            "chain findings, and reason through full multi-step attack paths")
    if f.foothold_analysis:
        caps.append("foothold analysis (what a described foothold enables next)")
    if f.multi_turn_scenarios:
        caps.append("complex, operator-inspired multi-turn engagement scenarios")
    if f.operator_tasks:
        caps.append("operator task reasoning (lateral movement, persistence, C2 concepts) within scope")
    if f.real_attack_vectors:
        caps.append("grounding in real attack vectors, threat intelligence, and operator-inspired tasks")
    if caps:
        parts.append("You are designed to handle: " + "; ".join(caps) + ".")

    if f.sensitive_content:
        parts.append(
            "You handle sensitive security content (exploit concepts, tradecraft, "
            "adversary behavior) for the authorized assessment instead of refusing "
            "by default, because refusal here breaks workflows and distorts analysis.")
    else:
        parts.append(
            "You keep content at an analytical level and avoid explicit, actionable "
            "sensitive tradecraft unless explicitly required by the authorized task.")

    if g.allowed_categories:
        parts.append("In-scope categories: " + ", ".join(g.allowed_categories) + ".")

    parts.append(
        f"Authorization scope: {g.authorization_scope}. Guardrail level: "
        f"{g.guardrail_level}. Treat this scope as a hard boundary.")
    if g.refuse_outside_scope:
        parts.append("Refuse or redirect anything outside this scope and explain why.")

    extra_denied = [c for c in g.denied_categories if c]
    parts.append(_floor_line(extra_denied))
    parts.append(
        "When you advise on an attack path, frame it for authorized assessment, "
        "detection, and hardening so the same reasoning serves defense and offense.")
    return _append_success_criteria(" ".join(parts), params.success_criteria)


def _append_success_criteria(prompt: str, criteria: list[str]) -> str:
    """Bake the user's model-level definition of success into its behavior."""
    if not criteria:
        return prompt
    if not isinstance(criteria, list) or not all(isinstance(item, str) for item in criteria):
        raise ValueError("success_criteria must be a list of strings")
    from .prompt_guide import validate_success_criteria
    criteria = validate_success_criteria(criteria)
    lines = [prompt, "", "<success_criteria>"]
    lines.extend(f"- {criterion}" for criterion in criteria)
    lines.extend([
        "</success_criteria>",
        "For every answer, verify these criteria against evidence. Label each pass, "
        "fail, uncertain, or not-tested; never invent facts, sources, or completion.",
    ])
    return "\n".join(lines)


def _floor_line(extra=None) -> str:
    cats = list(_HARD_FLOOR) + [c for c in (extra or []) if c]
    return "Always refuse, regardless of scope: " + "; ".join(cats) + "."


# ---------------------------------------------------------------------------
# Help / guidance so the user can actually set their parameters
# ---------------------------------------------------------------------------
PARAMETER_GUIDE = [
    ("success_criteria", "Required model acceptance criteria: observable outcomes, evaluation methods, and target thresholds."),
    ("base_model", "Base open-weights model to fine-tune (llama3.1-8b, qwen2.5-7b, mistral-7b, qwen2.5-14b, llama3.1-70b, phi3-mini)."),
    ("method", "Fine-tuning method: qlora (cheap, default), lora, or full (expensive)."),
    ("epochs", "Passes over the data. 1-3 cheap, 3-6 thorough, more risks overfitting."),
    ("learning_rate", "Step size. ~2e-4 QLoRA, ~1e-4 LoRA, ~1e-5 to 5e-5 full FT."),
    ("batch_size", "Examples per step. Lower (1-2) if you OOM on your GPU."),
    ("gradient_accumulation_steps", "Accumulate gradients to simulate a larger batch without more VRAM."),
    ("max_seq_len", "Max tokens per example. 2048 cheap; 4096-8192 helps long multi-turn cyber scenarios."),
    ("lora_r", "LoRA rank. 8 tiny, 16-32 balanced, 64+ high capacity (more VRAM)."),
    ("lora_alpha", "LoRA scaling. A common rule is 2x lora_r."),
    ("lora_dropout", "0.05-0.1 regularizes and reduces overfitting."),
    ("weight_decay", "0.0-0.1 L2 regularization."),
    ("warmup_ratio", "0.0-0.1 of steps used to ramp up the learning rate."),
    ("lr_scheduler", "cosine (common), linear, constant, cosine_with_restarts."),
    ("optimizer", "adamw_torch, paged_adamw_8bit (saves VRAM), adafactor."),
    ("seed", "Reproducibility seed (any integer)."),
    ("packing", "Pack short examples together (faster) - true/false."),
    ("dataset_ids", "Hugging Face repo ids to train on, including user-registered datasets."),
    ("focus.*", "Cyber capability toggles (offensive_reasoning, adversary_modeling, attack_path_reasoning, multi_turn_scenarios, sensitive_content, foothold_analysis, operator_tasks, real_attack_vectors)."),
    ("guardrails.authorization_confirmed", "You affirmed you are authorized to operate."),
    ("guardrails.authorization_scope", "The declared scope the model may operate in."),
    ("guardrails.guardrail_level", "authorized-lab | red-team-engagement | research-only | unrestricted-with-disclosure."),
    ("guardrails.allowed_categories", "Capability categories the model may reason about."),
    ("guardrails.denied_categories", "Extra categories to always refuse (on top of the safety floor)."),
    ("guardrails.refuse_outside_scope", "true = refuse/redirect anything outside scope."),
]


def guide_text() -> str:
    """Return a human-readable guide of every tunable parameter."""
    width = max(len(name) for name, _ in PARAMETER_GUIDE)
    lines = ["RoboDaddy parameters - you can set any of these:", ""]
    for name, desc in PARAMETER_GUIDE:
        lines.append(f"  {name.ljust(width)}  {desc}")
    lines.append("")
    lines.append("Hard safety floor (always refused, not configurable):")
    for cat in _HARD_FLOOR:
        lines.append(f"  - {cat}")
    return "\n".join(lines)


def apply_to_plan_dict(plan_dict: dict, params: ModelParameters,
                       *, system_prompt: str) -> dict:
    """Overlay non-None user parameters onto a plan dict."""
    for key in ("epochs", "learning_rate", "batch_size", "max_seq_len", "lora_r"):
        val = getattr(params, key, None)
        if val is not None:
            plan_dict[key] = val
    if params.method and params.method in ("qlora", "lora", "full"):
        plan_dict["method"] = params.method
    plan_dict["system_prompt"] = system_prompt
    plan_dict["success_criteria"] = list(params.success_criteria)
    plan_dict["focus"] = params.focus.to_dict()
    plan_dict["guardrails"] = params.guardrails.to_dict()
    extra = {}
    for key in ("lora_alpha", "lora_dropout", "weight_decay", "warmup_ratio",
                "gradient_accumulation_steps", "lr_scheduler", "optimizer", "seed",
                "packing"):
        val = getattr(params, key, None)
        if val is not None:
            extra[key] = val
    plan_dict["extra_hyperparams"] = extra
    return plan_dict


def merge_overrides(params: ModelParameters, **overrides) -> ModelParameters:
    """Return a copy of params with simple scalar overrides applied.

    Supports dotted keys like 'focus.sensitive_content' and 'guardrails.guardrail_level'.
    """
    d = params.to_dict()
    for key, value in overrides.items():
        if value is None:
            continue
        if "." in key:
            section, field_name = key.split(".", 1)
            if section in d and isinstance(d[section], dict) and field_name in d[section]:
                d[section][field_name] = value
        elif key in d:
            if key == "success_criteria":
                from .prompt_guide import validate_success_criteria
                value = validate_success_criteria(value)
            d[key] = value
    focus = CyberFocus(**(d.get("focus") or {}))
    gr = Guardrails(**(d.get("guardrails") or {}))
    rest = {k: v for k, v in d.items() if k not in ("focus", "guardrails")}
    return ModelParameters(focus=focus, guardrails=gr, **rest)
