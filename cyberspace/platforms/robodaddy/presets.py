"""Use-case presets for RoboDaddy.

Maps a model-building request to a concrete recipe: base model, recommended
dataset group, training method, and typical GPU class.
"""
from __future__ import annotations

# Base models are real open-weight HF repos (param count drives GPU choice).
BASE_MODELS = {
    "llama3.1-8b":  {"hf": "meta-llama/Llama-3.1-8B", "billion": 8,
                     "license": "llama3.1", "note": "Strong general base, tool-capable."},
    "llama3.1-70b": {"hf": "meta-llama/Llama-3.1-70B", "billion": 70,
                     "license": "llama3.1", "note": "Frontier-grade; needs H100/A100-80."},
    "qwen2.5-7b":   {"hf": "Qwen/Qwen2.5-7B", "billion": 7,
                     "license": "apache-2.0", "note": "Great coder + multilingual."},
    "qwen2.5-14b":  {"hf": "Qwen/Qwen2.5-14B", "billion": 14,
                     "license": "apache-2.0", "note": "Quality/size sweet spot."},
    "mistral-7b":   {"hf": "mistralai/Mistral-7B-v0.3", "billion": 7,
                     "license": "apache-2.0", "note": "Solid, permissive base."},
    "phi3-mini":    {"hf": "microsoft/Phi-3-mini-4k-instruct", "billion": 4,
                     "license": "mit", "note": "Tiny + fast - cheap to train."},
}

# Preset key -> recipe. prompt_examples are the things a user might type.
PRESETS = {
    "offensive_pentest": {
        "label": "Authorized Offensive Security",
        "prompt_examples": ["offensive pen security", "red team", "authorized testing",
                            "authorized red team", "red team assistant", "pentest assistant"],
        "base": "llama3.1-8b", "method": "qlora",
        "datasets": "offensive_pentest",
        "system_prompt": "You are a senior offensive security operator. Help plan "
                         "authorized assessments using available tools.",
    },
    "defensive_pentest": {
        "label": "Defensive / Blue Team Security",
        "prompt_examples": ["defensive pen security", "blue team", "soc analyst",
                            "soc", "detection engineer"],
        "base": "qwen2.5-7b", "method": "qlora",
        "datasets": "defensive_pentest",
        "system_prompt": "You are a defensive security analyst focused on detection, "
                         "triage, and hardening.",
    },
    "personal_assistant": {
        "label": "Personal Assistant",
        "prompt_examples": ["personal assistant", "productivity ai", "secretary"],
        "base": "qwen2.5-14b", "method": "qlora",
        "datasets": "personal_assistant",
        "system_prompt": "You are a warm, capable personal assistant.",
    },
    "creative_roleplay": {
        "label": "Creative / Roleplay Companion",
        "prompt_examples": ["companion", "roleplay ai", "character"],
        "base": "qwen2.5-14b", "method": "qlora",
        "datasets": "creative_roleplay",
        "system_prompt": "You are an expressive, in-character roleplay companion.",
    },
    "code": {
        "label": "Coding / Engineering",
        "prompt_examples": ["code ai", "code model", "coding model", "code review",
                            "developer assistant", "copilot"],
        "base": "qwen2.5-7b", "method": "qlora",
        "datasets": "code",
        "system_prompt": "You are an expert software engineer. Write clean, correct code.",
    },
    "general": {
        "label": "General / Custom",
        "prompt_examples": ["general", "custom", "anything"],
        "base": "llama3.1-8b", "method": "qlora",
        "datasets": "general",
        "system_prompt": "",
    },
}


def match_preset(prompt: str) -> str:
    """Best preset key for a free-text intent (case-insensitive substring match)."""
    p = _normalize(prompt)
    if not p:
        return "general"
    best, best_score = "general", 0
    for key, preset in PRESETS.items():
        score = 0
        for ex in preset["prompt_examples"]:
            normalized = _normalize(ex)
            if normalized and normalized in p:
                score += len(normalized)
        if score > best_score:
            best, best_score = key, score
    return best


def preset_for(key: str) -> dict:
    return PRESETS.get(key, PRESETS["general"])


def resolve_use_case(value: str) -> str:
    """Return a preset key from either an exact key or a free-text request."""
    value = (value or "").strip()
    if value in PRESETS:
        return value
    return match_preset(value)


def _normalize(value: str) -> str:
    chars = [c.lower() if c.isalnum() else " " for c in (value or "")]
    return " ".join("".join(chars).split())
