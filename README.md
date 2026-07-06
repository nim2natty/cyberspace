<p align="center">
  <img src=".github/banner.svg" width="100%" alt="cyberspace banner">
</p>

---

<p align="center">
  <strong>cyberspace</strong> is the first pentest platform that gives you a <em>swarm of specialized AI agents</em>,
  each commanding its own arsenal of tools — all from one clean command line.
</p>

<p align="center">
  <img alt="Python" src="https://img.shields.io/badge/Python-3.10+-blue?logo=python&logoColor=white">
  <img alt="License" src="https://img.shields.io/github/license/nim2natty/cyberspace?color=green">
  <img alt="Agents" src="https://img.shields.io/badge/agents-6%20specialists-a855f7">
  <img alt="Tools" src="https://img.shields.io/badge/tools-40%20interlinked-00d9ff">
  <img alt="Stars" src="https://img.shields.io/github/stars/nim2natty/cyberspace?style=social">
</p>

---

## What makes cyberspace different

There are plenty of AI pentest tools. Here's why cyberspace exists:

| Feature | cyberspace | PentestGPT (14k★) | Tandem | vulnhuntr (2.7k★) | hackingBuddyGPT (1.1k★) |
|---|:---:|:---:|:---:|:---:|:---:|
| **Multi-agent swarm** (6 specialists) | ✅ | ❌ single | ✅ 4 agents | ❌ | ❌ |
| **Hardware control** (ESP32 + FT232 + router) | ✅ | ❌ | ❌ | ❌ | ❌ |
| **OPSEC anti-detect browser** (Tor/dark web) | ✅ | ❌ | ❌ | ❌ | ❌ |
| **Train your own AI model** | ✅ | ❌ | ❌ | ❌ | ❌ |
| **Memory + personalization** (learns you) | ✅ | ❌ | ❌ | ❌ | ❌ |
| **Chain pipelines** (tools feed each other) | ✅ | ❌ | ❌ | ❌ | ❌ |
| **Any LLM** (local Ollama / OpenAI / Claude) | ✅ | OpenAI | 8 providers | OpenAI | OpenAI |
| **Runs on RPi5 / Kali Docker** | ✅ | ❌ | ❌ | ❌ | ❌ |

> **TL;DR:** others do one thing. cyberspace is the **all-in-one platform** — a team
> of agents that can scan your network, exploit a web app, browse the dark web
> anonymously, attack your WiFi hardware, AND train a custom AI to run it all.

## The swarm

When you run `cyberspace swarm`, you command a team through one Orchestrator:

```
                         ┌──────────────────────┐
                         │   ORCHESTRATOR        │  ← you talk to this
                         │   (mission commander) │
                         └──────────┬───────────┘
          ┌──────────┬─────────────┼──────────────┬─────────────┐
          ▼          ▼             ▼              ▼             ▼
     ┌────────┐ ┌────────┐  ┌───────────┐  ┌──────────┐  ┌────────┐
     │ Recon  │ │Exploit │  │  Ghost    │  │ Hardware │  │ Smith  │
     │  📶    │ │  🐍    │  │  🧊       │  │  🔌      │  │  👶    │
     │        │ │        │  │           │  │          │  │        │
     │nmap    │ │sqlmap  │  │anti-detect│  │ESP32     │  │train   │
     │masscan │ │metasp. │  │Tor/darkweb│  │FT232     │  │fine-   │
     │chains  │ │chains  │  │OSINT      │  │OpenWrt   │  │tune    │
     └────────┘ └────────┘  └───────────┘  └──────────┘  └────────┘
                                                      ┌────────┐
                                                      │ Scribe │  ← writes the report
                                                      │  📝    │
                                                      └────────┘
```

Each agent has its **own persona, scoped tools, and system prompt**. The Orchestrator
breaks your objective into phases and delegates each to the right specialist,
chaining their outputs together.

**Example:** *"Scan 10.10.10.0/24, find the web app, test it, write a report."*
→ **Recon** (discovers hosts + web app) → **Exploit** (tests the app) → **Scribe** (report).

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

Every platform is a super-tool with **interlinked commands** — tools chain together
so one step's output feeds the next.

| Platform | Agent | What it does |
|---|:---:|---|
| **AirBender** 📶 | Recon | ALL networking tools (nmap, masscan, aircrack-ng, netcat, dig...) chained into pipelines. `recon` runs ping-sweep → port-scan → service-detect in one go. |
| **ShadowDragon** 🐍 | Exploit | ALL non-networking Kali tools + **Metasploit**. Chain whatweb → searchsploit → msfconsole. Includes web, password, recon, post-exploit, forensics, RE. |
| **IceBerg** 🧊 | Ghost | OPSEC anti-detect browser (canvas/WebGL/WebRTC spoofing, DoH, fingerprint profiles) + **:: secure** AI find (brightside clearnet / darkside Tor OSINT). |
| **StickEm** 🔌 | Hardware | ESP32 Marauder + FT232 + **OpenWrt router** — three hardware interfaces unified. WiFi attacks, serial console, router config from one command. |
| **TrainABaby** 👶 | Smith | Train your **own** AI model: pick a dataset, rent a cloud GPU (Vast.ai), fine-tune, serve behind an API key, and plug it back into the swarm. |

## Micro-features that add up

- **🧠 Memory + personalization** — remembers your tools, targets, and skill level across sessions. Injects it into the agent prompt so it needs *fewer prompts over time*. `cyberspace memory show`
- **🔗 Chain pipelines** — `airbender recon 10.10.10.0/24` runs ping-sweep → nmap → service-detect automatically. `shadowdragon full-assault` runs whatweb → gobuster → nikto → searchsploit → metasploit.
- **⚡ Model switching** — swap the active LLM: `cyberspace iceberg model switch qwen2.5-coder:7b`
- **📊 Engagement reports** — `cyberspace report --out report.md` generates a markdown report from activity history
- **🚀 Quickstart** — `cyberspace quickstart` configures + launches in one step
- **🔄 Model training loop** — train → serve → `cyberspace trainababy use <model>` makes it the swarm's brain
- **🎛️ RoE support** — `cyberspace swarm --roe engagement.md`

## Why it's great for learning

Maps to **CompTIA PenTest+** domains: Info Gathering (AirBender), Vulnerability ID & Attacks (ShadowDragon), Reporting (Scribe), OPSEC (IceBerg). The agent-first design also teaches the modern **agentic offensive workflow**.

## ⚠️ For legal security education and authorized assessments only

Practice against your own lab (DVWA, Juice Shop, GOAD, your own router/AP) or systems you have written permission to test.

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

