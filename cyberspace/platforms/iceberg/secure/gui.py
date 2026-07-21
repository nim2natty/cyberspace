"""Streamlit GUI for Iceberg's AI-powered find and browse experience.

Launched by:  cyberspace iceberg gui
(which runs:  streamlit run <this file>)

This is the graphic interface for the optimal IceBerg browsing experience: pick
brightside (clearnet) or darkside (Tor), review/lock the security posture, then
run the AI find pipeline with live streaming-style status and a downloadable
structured summary.
"""
from __future__ import annotations

# NOTE: absolute imports so this also works when invoked via `streamlit run`.
import json

import streamlit as st

from cyberspace.platforms.iceberg.secure.intel import PRESET_LABELS
from cyberspace.platforms.iceberg.secure.pipeline import (
    Investigation,
    list_investigations,
    run_find,
    save_investigation,
)
from cyberspace.platforms.iceberg.secure.security import (
    PRESETS,
    SecurityConfig,
    dark_settings,
)
from cyberspace.platforms.iceberg.secure.tor import tor_available


st.set_page_config(page_title="Iceberg privacy", page_icon="🧊", layout="wide")

# --- Sidebar: mode + security posture --------------------------------------
with st.sidebar:
    st.title("🧊 Iceberg")
    st.caption("AI-powered find & browse  ·  brightside / darkside")

    preset_key = st.selectbox(
        "Browsing mode", list(PRESETS.keys()),
        format_func=lambda k: PRESETS[k]["label"], index=0)
    sec: SecurityConfig = PRESETS[preset_key]["config"]

    with st.expander("🔒 Security posture", expanded=(sec.mode == "dark")):
        if sec.mode == "dark":
            for line in dark_settings(sec):
                st.caption("• " + line)
            st.caption(f"Tor proxy: "
                       f"{'🟢 reachable' if tor_available(sec.tor_socks_host, sec.tor_socks_port) else '🔴 not running'}")
        else:
            st.caption("• transport: direct clearnet (no Tor)")
            st.caption("• WebRTC blocked, DoH on, UA rotation on")

        sec.new_identity_per_session = st.checkbox(
            "New Tor identity each run", value=sec.new_identity_per_session,
            disabled=(sec.mode != "dark"))
        sec.max_results = st.slider("Max search results", 5, 50, sec.max_results)
        sec.max_scrape = st.slider("Max pages to scrape", 2, 15, sec.max_scrape)

    st.divider()
    preset = st.selectbox("Analysis preset", list(PRESET_LABELS.keys()),
                          format_func=lambda k: PRESET_LABELS[k], index=3)
    custom = st.text_input("Extra focus (optional)", placeholder="e.g. focus on 2024 breaches")

    st.divider()
    st.caption("For LEGAL security education and authorized OSINT only.")


# --- Main: the find pipeline -----------------------------------------------
st.header("🔎 AI find")
query = st.text_input("What are you investigating?", placeholder="e.g. ransomware leaked credentials acme corp")

if st.button("Run investigation", type="primary", disabled=not query.strip()):
    sec.save()
    status = st.status("Running AI find pipeline...", expanded=True)
    events: list[tuple[str, str]] = []

    def on_event(stage: str, msg: str) -> None:
        events.append((stage, msg))
        status.update(label=f"{stage}: {msg}")

    inv: Investigation = run_find(query.strip(), sec=sec, preset=preset,
                                  custom=custom, on_event=on_event)
    status.update(label="Investigation complete", state="complete")

    if inv.saved_path is None and inv.summary:
        save_investigation(inv)

    st.subheader("📝 Findings")
    st.caption(f"refined query: `{inv.refined}`  ·  "
               f"results: {len(inv.results)}  ·  filtered: {len(inv.filtered)}  ·  "
               f"scraped: {len(inv.scraped)}")
    st.markdown(inv.summary or "_(no summary)_")

    with st.expander(f"🔗 Sources ({len(inv.filtered)})"):
        for i, s in enumerate(inv.filtered, 1):
            st.markdown(f"{i}. [{s.get('title','Untitled')}]({s.get('link','')})")

    with st.expander("🎛️ Pipeline log"):
        for stage, msg in events:
            st.text(f"[{stage}] {msg}")

# --- Past investigations ---------------------------------------------------
past = list_investigations()
if past:
    st.divider()
    with st.expander(f"📂 Past investigations ({len(past)})"):
        for p in past[:10]:
            st.markdown(f"**{p.get('query','?')}** "
                        f"`{p.get('mode','?')}` · {p.get('_file','')}")
            st.caption(p.get("summary", "")[:160] + "…")
