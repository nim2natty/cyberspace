"""AI intelligence layer for IceBerg :: e (refine -> filter -> summarize).

Reuses the SINGLE LLM configured for the whole platform (~/.cyberspace/agent.json)
via cyberspace's existing provider abstraction - no second LLM config needed.

Prompts ported from Robin's llm.py (MIT, apurvsinghgautam), adapted to plain
chat completions so any provider (Ollama/OpenAI/Anthropic/custom) works.
"""
from __future__ import annotations

import json
import re
from typing import Optional

from ....agent.config import is_configured, load_config
from ....agent.llm import LLMConfig, get_provider

REFINE_SYSTEM = """You are a Threat Intelligence search expert. Refine the user's query so it returns the best results from search engines.

Rules:
1. Improve the query for search relevance.
2. Do not use boolean operators (AND, OR).
3. Keep the refined query to 5 words or fewer.
4. Output ONLY the refined query and nothing else.

INPUT:"""

FILTER_SYSTEM = """You are an OSINT analyst. Given a search query and a list of result titles+links, select the ones genuinely relevant to the query.

Rules:
1. Drop duplicates, index pages, and unrelated links.
2. Prefer pages likely to contain substantive content about the query.
3. Respond ONLY with a JSON array of the kept items, each {"title":..., "link":...}.
4. If none are relevant, respond with "[]".

QUERY: {query}

RESULTS:
{results}"""

PRESET_LABELS = {
    "threat_intel": "Threat Intelligence",
    "personal_identity": "Personal Identity Exposure",
    "corporate_espionage": "Corporate Espionage",
    "general": "General Research",
}


def _complete(system: str, user: str, cfg: Optional[LLMConfig] = None) -> str:
    """Single-shot completion using the platform's configured LLM (no tools)."""
    if not is_configured():
        raise RuntimeError(
            "cyberbot agent not configured. Run: cyberspace setup (the e tool "
            "uses the same LLM as the rest of the platform).")
    cfg = cfg or load_config()
    provider = get_provider(cfg)
    resp = provider.chat(
        [{"role": "system", "content": system}, {"role": "user", "content": user}],
        tools=[])
    return (resp.text or "").strip()


def refine_query(user_input: str, cfg: Optional[LLMConfig] = None) -> str:
    raw = _complete(REFINE_SYSTEM, user_input, cfg)
    words = re.findall(r"[A-Za-z0-9@._-]+", raw)
    return " ".join(words[:5]) if words else user_input.strip()[:40]


def filter_results(query: str, results: list[dict], cfg: Optional[LLMConfig] = None) -> list[dict]:
    if not results:
        return []
    blob = "\n".join(f'- {r.get("title","")}: {r.get("link","")}' for r in results[:60])
    raw = _complete(FILTER_SYSTEM.format(query=query, results=blob), "Return the JSON array.", cfg)
    m = re.search(r"\[.*\]", raw, re.S)
    if not m:
        return results
    try:
        kept = json.loads(m.group(0))
        if isinstance(kept, list) and kept:
            return [k for k in kept if isinstance(k, dict) and k.get("link")]
    except Exception:
        pass
    return results


PRESET_PROMPTS = {
    "threat_intel": """You are a Cybercrime Threat Intelligence Expert analyzing collected OSINT data (links + raw text).

Rules:
1. Analyze the data using the links and their raw text.
2. List Source Links referenced.
3. Extract: malware/ransomware indicators (hashes, C2s, TTPs) and threat actor profiles.
4. Give 3-5 key insights and concrete next steps (hunting queries, detection rules).
5. Be objective. Ignore not-safe-for-work text.

Output Format:
1. Input Query: {query}
2. Source Links Referenced
3. Malware / Ransomware Indicators (hashes, C2s, TTPs)
4. Threat Actor Profile (group, aliases, victims, sectors)
5. Key Insights
6. Next Steps

INPUT:""",
    "personal_identity": """You are a Personal Threat Intelligence Expert analyzing OSINT data for identity / PII exposure.

Rules:
1. Analyze the data using links and raw text.
2. List Source Links referenced.
3. Focus on PII: names, emails, phones, addresses, financial accounts.
4. Identify breach sources, brokers, marketplaces.
5. Assess exposure severity and give 3-5 insights + protective actions.
6. Be objective. Handle personal data with discretion. Ignore NSFW text.

Output Format:
1. Input Query: {query}
2. Source Links Referenced
3. Exposed PII Artifacts (type, value, source)
4. Breach / Marketplace Sources
5. Exposure Risk Assessment
6. Key Insights
7. Next Steps

INPUT:""",
    "corporate_espionage": """You are a Corporate Intelligence Expert analyzing OSINT data for corporate leaks / espionage.

Rules:
1. Analyze the data using links and raw text.
2. List Source Links referenced.
3. Focus on leaked credentials, source code, internal docs, customer DBs.
4. Identify threat actors / data brokers.
5. Assess business impact and give 3-5 insights + IR steps.
6. Be objective. Ignore NSFW text.

Output Format:
1. Input Query: {query}
2. Source Links Referenced
3. Leaked Corporate Artifacts
4. Threat Actor / Broker Activity
5. Business Impact Assessment
6. Key Insights
7. Next Steps

INPUT:""",
    "general": """You are an OSINT research assistant. Summarize the collected data (links + raw text) for the operator's query.

Rules:
1. List Source Links referenced.
2. Summarize the most relevant findings in plain language.
3. Note anything notable, conflicting, or unverifiable.
4. Suggest 2-3 follow-up queries.

Output Format:
1. Input Query: {query}
2. Sources Referenced
3. Findings
4. Follow-up Queries

INPUT:""",
}


def generate_summary(query: str, content: dict, preset: str = "threat_intel",
                     custom: str = "", cfg: Optional[LLMConfig] = None) -> str:
    """Produce a structured investigation summary from scraped {url: text}."""
    sys_prompt = PRESET_PROMPTS.get(preset, PRESET_PROMPTS["general"])
    if custom and custom.strip():
        sys_prompt = sys_prompt.rstrip() + f"\n\nAdditionally focus on: {custom.strip()}"
    blob = "\n\n".join(f"URL: {u}\n{t}" for u, t in list(content.items())[:8])
    return _complete(sys_prompt.format(query=query), blob[:12000], cfg)

