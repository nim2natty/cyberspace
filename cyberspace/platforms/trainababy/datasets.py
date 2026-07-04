"""Public training datasets catalog for TrainABaby.

These are REAL open datasets used to fine-tune open-source LLMs (Hugging Face Hub
repos). Organized by use case so a preset can recommend the right data. Each entry
names the real HF repo, its rough size, license, and the role it plays.

We do NOT bundle the data; `train.py` references these repos and the training
script pulls them with `datasets.load_dataset(...)` on the rented GPU.
"""
from __future__ import annotations

# use_case -> [dataset entries]. id == the HF repo id you'd pass to load_dataset.
DATASETS = {
    "offensive_pentest": [
        {"id": "wikihow/wikihow", "name": "How-to instruction set",
         "size": "~200k pairs", "license": "CC-BY-NC-SA",
         "note": "General instruction following - builds the agent's step-by-step skill."},
        {"id": "garage-bAInd/Open-Platypus", "name": "Open-Platypus",
         "size": "~25k pairs", "license": "various (open)",
         "note": "STEM/reasoning instruction set - good base for tool-use + exploit logic."},
        {"id": "MaziyarPanahi/instruction-dataset", "name": "Misc instruction",
         "size": "~50k pairs", "license": "apache-2.0",
         "note": "Broad instruction-tuning to make the model cooperative and agent-ready."},
    ],
    "defensive_pentest": [
        {"id": "HuggingFaceH4/no_robots", "name": "no_robots",
         "size": "~10k pairs", "license": "apache-2.0",
         "note": "High-quality human-written instructions; safe, refusal-aware base."},
        {"id": "allenai/sciq", "name": "SciQ",
         "size": "~13k items", "license": "CC-BY-SA",
         "note": "Reasoning + evidence - good for detection/threat-analysis thinking."},
        {"id": "garage-bAInd/Open-Platypus", "name": "Open-Platypus",
         "size": "~25k pairs", "license": "various (open)",
         "note": "Reasoning backbone for IR playbooks / detection-rule authoring."},
    ],
    "personal_assistant": [
        {"id": "tatsu-lab/alpaca", "name": "Alpaca",
         "size": "~52k pairs", "license": "apache-2.0",
         "note": "The classic instruction-tuning set. Friendly, general assistant base."},
        {"id": "HuggingFaceH4/ultrachat_200k", "name": "UltraChat 200k",
         "size": "~200k convs", "license": "CC-BY-NC-4.0",
         "note": "Multi-turn chat - makes the assistant conversational."},
        {"id": "teknium/OpenHermes-2.5", "name": "OpenHermes 2.5",
         "size": "~1M pairs", "license": "MIT",
         "note": "Large, high-quality general SFT set. Strong all-rounder."},
    ],
    "code": [
        {"id": "nickrosh/Evol-Instruct-Code-80k-v1", "name": "Evol-Instruct-Code",
         "size": "~80k pairs", "license": "apache-2.0",
         "note": "Code instruction - for writing scripts/exploits/tooling."},
        {"id": "codeparrot/github-code", "name": "github-code",
         "size": "millions of files", "license": "various",
         "note": "Raw code corpus (CCL); good for continued pretraining."},
    ],
    "creative_roleplay": [
        {"id": "HuggingFaceH4/ultrachat_200k", "name": "UltraChat 200k",
         "size": "~200k convs", "license": "CC-BY-NC-4.0",
         "note": "Conversational depth for character/persona play."},
        {"id": "teknium/OpenHermes-2.5", "name": "OpenHermes 2.5",
         "size": "~1M pairs", "license": "MIT",
         "note": "General quality base for expressive responses."},
    ],
    "general": [
        {"id": "databricks/databricks-dolly-15k", "name": "Dolly 15k",
         "size": "~15k pairs", "license": "CC-BY-SA-3.0",
         "note": "Crowd-written instruction - compact, clean, free to use."},
        {"id": "Open-Orca/OpenOrca", "name": "OpenOrca",
         "size": "~4M pairs", "license": "MIT",
         "note": "GPT-3.5-style distillation; very common SFT base."},
    ],
}


def datasets_for(use_case: str) -> list[dict]:
    return list(DATASETS.get(use_case, DATASETS["general"]))


def all_datasets() -> dict[str, list[dict]]:
    return {k: list(v) for k, v in DATASETS.items()}
