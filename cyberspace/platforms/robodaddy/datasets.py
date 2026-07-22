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
    # Also check user-registered custom Hugging Face datasets.
    custom = _custom_dataset_by_id(dataset_id)
    if custom:
        return dict(custom)
    # If nothing is known about it, return a permissive entry so the user can
    # still enter any Hugging Face repo id (RoboDaddy accepts any
    # curated catalog). The generated training script handles the real schema.
    if "/" in dataset_id:
        return {
            "id": dataset_id, "name": dataset_id.rsplit("/", 1)[-1],
            "size": "unknown", "license": "unknown",
            "access": "check Hugging Face", "schema": "inspect before training",
            "note": f"User-selected Hugging Face dataset {dataset_id}. Verify its "
                    "license, access terms, and schema before a real training run.",
        }
    return {}


# ---------------------------------------------------------------------------
# User-registered Hugging Face datasets (enter any repo id)
# ---------------------------------------------------------------------------
def _custom_file():
    from ...config import MODULES_DIR, ensure_dirs
    ensure_dirs()
    return MODULES_DIR / "robodaddy" / "custom_datasets.json"


def custom_datasets() -> list[dict]:
    """Return datasets the user has registered (any Hugging Face repo id)."""
    import json
    try:
        path = _custom_file()
        if not path.exists():
            return []
        data = json.loads(path.read_text())
        return data if isinstance(data, list) else []
    except Exception:
        return []


def register_dataset(dataset_id: str, *, name: str = "", size: str = "unknown",
                     license: str = "unknown", access: str = "check Hugging Face",
                     schema: str = "inspect before training", note: str = "",
                     use_case: str = "general") -> dict:
    """Register any Hugging Face dataset so it shows up alongside the catalog.

    This is how a user picks an arbitrary dataset on the Hub: register it, then it
    is searchable and selectable just like the curated entries. RoboDaddy does not
    limit you to the built-in catalog.
    """
    import json
    dataset_id = (dataset_id or "").strip()
    if "/" not in dataset_id:
        raise ValueError("dataset id must be a Hugging Face repo id like 'owner/name'")
    entry = {
        "id": dataset_id, "name": name or dataset_id.rsplit("/", 1)[-1],
        "size": size, "license": license, "access": access, "schema": schema,
        "note": note or f"User-registered Hugging Face dataset {dataset_id}.",
        "use_case": use_case, "source": "user-registered",
    }
    path = _custom_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = [d for d in custom_datasets() if d.get("id") != dataset_id]
    existing.append(entry)
    path.write_text(json.dumps(existing, indent=2))
    return entry


def _custom_dataset_by_id(dataset_id: str) -> dict:
    for d in custom_datasets():
        if d.get("id") == dataset_id:
            return dict(d)
    return {}


def search_datasets(query: str, limit: int = 10) -> list[dict]:
    """Fuzzy keyword search across ALL datasets.

    Ranks every dataset by how well it matches the free-text query. Matching is
    done against the dataset name, HF id, description note, and its use-case
    label - so the user can type anything natural ("python coding data",
    "blue team alerts", "chat assistant") and get the most relevant results back,
    regardless of which use-case bucket the dataset lives in.

    Each result is the dataset dict plus ``use_case`` and ``score`` fields.
    """
    from .presets import PRESETS

    tokens = _search_tokens(query)
    results: list[dict] = []

    searchable: dict[str, list[dict]] = {k: list(v) for k, v in DATASETS.items()}
    # Include any Hugging Face datasets the user registered, so they are
    # searchable/selectable just like the curated catalog.
    from .datasets import custom_datasets  # local import to avoid cycles
    if custom_datasets():
        searchable["user_registered"] = custom_datasets()

    for use_case, entries in searchable.items():
        label = PRESETS.get(use_case, {}).get("label", use_case)
        for d in entries:
            haystack = " ".join([
                d.get("name", ""), d.get("id", ""), d.get("note", ""),
                d.get("schema", ""), d.get("size", ""), label, use_case,
            ]).lower()
            score = 0
            for tok in tokens:
                if not tok:
                    continue
                # Stronger weight for name/id hits, lighter for note hits.
                if tok in d.get("name", "").lower() or tok in d.get("id", "").lower():
                    score += 5
                elif tok in label.lower() or tok in use_case.lower():
                    score += 3
                elif tok in haystack:
                    score += 1
            if score > 0 or not tokens:
                r = dict(d)
                r["use_case"] = use_case
                r["use_case_label"] = label
                r["score"] = score
                results.append(r)

    # No query + no tokens: return everything ranked by use-case then name.
    results.sort(key=lambda r: (-r["score"], r["use_case"], r.get("name", "")))
    if limit and limit > 0:
        results = results[:limit]
    return results


def _search_tokens(query: str) -> list[str]:
    """Split a query into normalized search tokens (len >= 2)."""
    raw = (query or "").lower()
    tokens = [t for t in raw.replace("-", " ").split() if len(t) >= 2]
    return tokens


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
