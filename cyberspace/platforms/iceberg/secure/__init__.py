"""Iceberg's integrated AI find and Tor browsing implementation.

Adapts the open-source Robin OSINT engine (https://github.com/apurvsinghgautam/robin,
MIT, (c) apurvsinghgautam) into Iceberg. The agent-configured LLM refines a query,
searches (clearnet for "brightside", Tor onion engines for "darkside"), filters,
scrapes, and produces a structured investigation summary - plus an optional
Streamlit GUI and a Tor security-hardened browsing path.

  brightside  -> clear web search + AI find (no Tor)
  darkside    -> Tor onion search + AI find (SOCKS5h proxy, DoH, WebRTC lockdown)

For LEGAL security education and authorized OSINT/investigation only.
"""
