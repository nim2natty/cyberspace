"""Public training dataset catalog for RoboDaddy.

The catalog references Hugging Face datasets by repo id. Data is not bundled with
cyberspace; generated training scripts call `datasets.load_dataset(...)` on the
training host, so dataset licenses and access requirements remain upstream.
"""
from __future__ import annotations

# use_case -> [dataset entries]. id == the HF repo id passed to load_dataset.
# access is intentionally explicit because some strong cybersecurity datasets
# require accepting Hugging Face terms before a real training run can read them.
DATASETS = {
    "offensive_pentest": [
        {"id": "trendmicro-ailab/Primus-Instruct", "name": "Primus-Instruct",
         "size": "<1k chat records", "license": "odc-by",
         "access": "gated: accept HF terms", "schema": "messages",
         "note": "Cybersecurity SFT set for alert explanation, suspicious command analysis, security-event queries, and risk recommendations."},
        {"id": "trendmicro-ailab/Primus-Reasoning", "name": "Primus-Reasoning",
         "size": "1k-10k chat records", "license": "odc-by",
         "access": "gated: accept HF terms", "schema": "messages",
         "note": "Cyber threat intelligence reasoning and reflection data; useful for authorized assessment analysis, not payload generation."},
        {"id": "garage-bAInd/Open-Platypus", "name": "Open-Platypus",
         "size": "~25k pairs", "license": "various (open)",
         "access": "public", "schema": "instruction",
         "note": "General reasoning baseline for plans and tool-use explanations when a domain dataset is not available."},
    ],
    "defensive_pentest": [
        {"id": "trendmicro-ailab/Primus-Instruct", "name": "Primus-Instruct",
         "size": "<1k chat records", "license": "odc-by",
         "access": "gated: accept HF terms", "schema": "messages",
         "note": "Security operations tasks: alerts, suspicious commands, event queries, cloud misconfiguration findings, and recommendations."},
        {"id": "trendmicro-ailab/Primus-Reasoning", "name": "Primus-Reasoning",
         "size": "1k-10k chat records", "license": "odc-by",
         "access": "gated: accept HF terms", "schema": "messages",
         "note": "CTI-Bench-derived reasoning samples for threat-intelligence classification and explanation."},
        {"id": "HuggingFaceH4/no_robots", "name": "no_robots",
         "size": "~10k pairs", "license": "apache-2.0",
         "access": "public", "schema": "messages",
         "note": "Human-written assistant data for concise explanations and refusal-aware behavior."},
    ],
    "personal_assistant": [
        {"id": "tatsu-lab/alpaca", "name": "Alpaca",
         "size": "~52k pairs", "license": "apache-2.0",
         "access": "public", "schema": "instruction",
         "note": "The classic instruction-tuning set. Friendly, general assistant base."},
        {"id": "HuggingFaceH4/ultrachat_200k", "name": "UltraChat 200k",
         "size": "~200k convs", "license": "CC-BY-NC-4.0",
         "access": "public", "schema": "messages",
         "note": "Multi-turn chat - makes the assistant conversational."},
        {"id": "teknium/OpenHermes-2.5", "name": "OpenHermes 2.5",
         "size": "~1M pairs", "license": "MIT",
         "access": "public", "schema": "instruction",
         "note": "Large, high-quality general SFT set. Strong all-rounder."},
    ],
    "code": [
        {"id": "nickrosh/Evol-Instruct-Code-80k-v1", "name": "Evol-Instruct-Code",
         "size": "78.3k pairs", "license": "cc-by-nc-sa-4.0",
         "access": "public", "schema": "instruction/output",
         "note": "Instruction/output coding tasks for software-engineering assistants; non-commercial license."},
        {"id": "ise-uiuc/Magicoder-OSS-Instruct-75K", "name": "Magicoder OSS Instruct",
         "size": "75.2k pairs", "license": "mit",
         "access": "public", "schema": "problem/solution",
         "note": "OSS-Instruct code tasks across multiple languages; compatible with the generated SFT formatter."},
    ],
    "creative_roleplay": [
        {"id": "HuggingFaceH4/ultrachat_200k", "name": "UltraChat 200k",
         "size": "~200k convs", "license": "CC-BY-NC-4.0",
         "access": "public", "schema": "messages",
         "note": "Conversational depth for character/persona play."},
        {"id": "teknium/OpenHermes-2.5", "name": "OpenHermes 2.5",
         "size": "~1M pairs", "license": "MIT",
         "access": "public", "schema": "instruction",
         "note": "General quality base for expressive responses."},
    ],
    "general": [
        {"id": "databricks/databricks-dolly-15k", "name": "Dolly 15k",
         "size": "~15k pairs", "license": "CC-BY-SA-3.0",
         "access": "public", "schema": "instruction",
         "note": "Crowd-written instruction - compact, clean, free to use."},
        {"id": "Open-Orca/OpenOrca", "name": "OpenOrca",
         "size": "~4M pairs", "license": "MIT",
         "access": "public", "schema": "question/response",
         "note": "GPT-3.5-style distillation; very common SFT base."},
    ],
}


def datasets_for(use_case: str) -> list[dict]:
    return list(DATASETS.get(use_case, DATASETS["general"]))


def all_datasets() -> dict[str, list[dict]]:
    return {k: list(v) for k, v in DATASETS.items()}


def dataset_by_id(dataset_id: str) -> dict:
    for entries in DATASETS.values():
        for entry in entries:
            if entry["id"] == dataset_id:
                return dict(entry)
    return {}


def recommend_datasets(request: str = "", *, use_case: str = "", limit: int = 0) -> dict:
    """Return dataset recommendations for a free-text model request.

    The caller can pass either an explicit preset key (`use_case`) or natural
    language (`request`) such as "build a code review model". The response keeps
    the matched preset metadata beside the candidate dataset list so agents can
    explain why a dataset was offered.
    """
    from .presets import match_preset, preset_for, resolve_use_case

    key = resolve_use_case(use_case) if use_case else match_preset(request)
    preset = preset_for(key)
    entries = datasets_for(preset["datasets"])
    if limit and limit > 0:
        entries = entries[:limit]
    return {
        "request": request,
        "use_case": key,
        "label": preset["label"],
        "base_model": preset["base"],
        "method": preset["method"],
        "datasets": entries,
    }
