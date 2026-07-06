<p align="center">
  <img src=".github/banner.svg" width="100%" alt="cyberspace banner">
</p>

---

<p align="center">
  <strong>cyberspace</strong> is an agentic penetration-testing platform. An orchestrator agent
  delegates to a team of specialized sub-agents, each scoped to one toolset: network scanning,
  exploitation, OPSEC, hardware, or model training. Any LLM (local Ollama, OpenAI, Claude, custom).
</p>

<p align="center">
  <img alt="Python" src="https://img.shields.io/badge/Python-3.10+-blue?logo=python&logoColor=white">
  <img alt="License" src="https://img.shields.io/github/license/nim2natty/cyberspace?color=green">
  <img alt="Agents" src="https://img.shields.io/badge/agents-6-a855f7">
  <img alt="Tools" src="https://img.shields.io/badge/tools-40-00d9ff">
  <img alt="Stars" src="https://img.shields.io/github/stars/nim2natty/cyberspace?style=social">
</p>

---

## The swarm

`cyberspace swarm` starts the Orchestrator, which delegates to specialized sub-agents:

```
                         ┌──────────────────────┐
                         │   ORCHESTRATOR        │  ← you talk to this
                         │   delegates tasks     │
                         └──────────┬───────────┘
          ┌──────────┬─────────────┼──────────────┬─────────────┐
          ▼          ▼             ▼              ▼             ▼
     ┌────────┐ ┌────────┐  ┌───────────┐  ┌──────────┐  ┌────────┐
     │ Recon  │ │Exploit │  │  Ghost    │  │ Hardware │  │ Smith  │
     │  📶    │ │  🐍    │  │  🧊       │  │  🔌      │  │  👶    │
     │nmap    │ │sqlmap  │  │anti-detect│  │ESP32     │  │train   │
     │masscan │ │msfcon. │  │Tor/darkweb│  │FT232     │  │fine-   │
     │chains  │ │chains  │  │OSINT      │  │OpenWrt   │  │tune    │
     └────────┘ └────────┘  └───────────┘  └──────────┘  └────────┘
                                                      ┌────────┐
                                                      │ Scribe │  ← report
                                                      │  📝    │
                                                      └────────┘
```

Each sub-agent has a scoped toolset and a role-specific system prompt. The
Orchestrator receives your objective, breaks it into phases, and delegates each
phase to the appropriate agent, passing outputs forward.

**Example:** *"Scan 10.10.10.0/24, find the web app, test it, write a report."*
→ Recon (discover hosts + web app) → Exploit (test the app) → Scribe (report).

## Quick start

```bash
cyberspace quickstart    # one command — configure agent + launch the swarm

# Or step by step:
cyberspace setup         # pick your LLM (local Ollama, OpenAI, Claude, or custom)
cyberspace swarm         # command the team
```

<details>
<summary><b>Other install methods</b></summary>

```bash
# From source
git clone https://github.com/nim2natty/cyberspace && cd cyberspace
python3 -m venv .venv && source .venv/bin/activate
pip install -e . && playwright install chromium

# Docker
docker build -t cyberspace . && docker run -it --rm cyberspace swarm

# One-liner (Linux/macOS)
curl -fsSL https://raw.githubusercontent.com/nim2natty/cyberspace/main/installer/install.sh | bash
```
</details>

## The platforms

Each platform wraps a set of real tools behind a consistent CLI and agent-tool
interface. Tools within a platform chain together — one step's output feeds the
next via named pipeline steps.

| Platform | Agent | Tools |
|---|:---:|---|
| **AirBender** 📶 | Recon | nmap, masscan, aircrack-ng, netdiscover, netcat, dig, traceroute, tcpdump. Chain pipelines: `recon` (ping-sweep → nmap-top → service-detect), `fast-scan`, `web-hunt`. |
| **ShadowDragon** 🐍 | Exploit | All non-networking Kali tools: sqlmap, gobuster, whatweb, nikto, nuclei, john, hashcat, hydra, searchsploit, theharvester, + metasploit (msfconsole via resource scripts). Chain pipelines: `web-recon`, `full-assault`, `wp-assault`. |
| **IceBerg** 🧊 | Ghost | Anti-detect browser (canvas/WebGL/audio/WebRTC spoofing, DoH, fingerprint profiles) + `:: secure` AI find: brightside (clearnet search) / darkside (16 onion engines over Tor SOCKS5h). Adapted from [Robin](https://github.com/apurvsinghgautam/robin) (MIT). |
| **StickEm** 🔌 | Hardware | ESP32 Marauder (deauth, PMKID capture), FT232 serial console, OpenWrt router (SSH control: WiFi config, DHCP leases, packages). Router presets: openwrt-one, gl-inet, generic. |
| **TrainABaby** 👶 | Smith | Fine-tune a model on public HF datasets (Alpaca, OpenHermes, Dolly, Open-Platypus) with QLoRA on rented cloud GPUs (Vast.ai API). Serve behind an OpenAI-compatible endpoint + API key. Plug back into the agent as a `custom` provider. |

## Features

- **Memory** — every action is logged to `~/.cyberspace/memory/`. A user profile (preferred tools, targets, skill level) is built incrementally and injected into the agent's system prompt. `cyberspace memory show`
- **Chain pipelines** — `airbender recon 10.10.10.0/24` runs ping-sweep → nmap → service-detect. `shadowdragon full-assault http://target` runs whatweb → gobuster → nikto → searchsploit → metasploit.
- **Model switching** — `cyberspace iceberg model switch <name>` changes the active LLM without re-running setup.
- **Engagement reports** — `cyberspace report --out report.md` writes a markdown report from the activity log.
- **Quickstart** — `cyberspace quickstart` configures the agent and launches the swarm in one command.
- **RoE support** — `cyberspace swarm --roe engagement.md` loads a Rules of Engagement file.

## CompTIA PenTest+ alignment

The platform maps to the PenTest+ domains:

| Domain | Platform |
|---|---|
| Information Gathering & Vulnerability Scanning | AirBender (Recon) |
| Attacks & Exploits | ShadowDragon (Exploit) |
| Reporting & Communication | Scribe |
| Tools & Code Analysis | ShadowDragon |
| OPSEC | IceBerg (Ghost) |

## Legal use only

For authorized security education and assessments only. Practice against your own
lab (DVWA, Juice Shop, GOAD, your own router/AP) or systems you have written
permission to test. Wireless attacks and Tor access target only networks you own.

## 🗂️ Project layout

```
cyberspace/
├── swarm.py                      # multi-agent orchestration (Orchestrator + 6 sub-agents)
├── memory.py                     # personalization (profile, episodes, semantic facts)
├── agent/                        # LLM providers (ollama/openai/anthropic/custom)
├── platforms/
│   ├── airbender/                # 📶 networking super-tool + chain engine
│   ├── shadowdragon/             # 🐍 ALL Kali tools + metasploit + chain
│   ├── iceberg/secure/           # 🧊 OPSEC + anti-detect + :: secure AI find
│   ├── stickem/                  # 🔌 ESP32 + FT232 + OpenWrt router
│   └── trainababy/               # 👶 train your own model
├── ui/dashboard.py               # the swarm hub (tandem-style control plane)
├── host.py                       # safe host-tool runner (no shell injection)
└── installer/                    # install.sh + Dockerfile + RPi5 recipe
```

## Contributing

PRs welcome. The plugin system auto-discovers any `cyberspace_module_*` package.

## License

MIT — see [LICENSE](LICENSE).

