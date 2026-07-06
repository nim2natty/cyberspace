<p align="center">
  <img src=".github/banner.svg" width="100%" alt="cyberspace banner">
</p>

---

<p align="center">
  <strong>cyberspace</strong> is an agentic security lab platform for authorized testing.
  A single orchestrator delegates work to specialized sub-agents with scoped tool access:
  reconnaissance, exploitation tooling, OPSEC, hardware, model training, and reporting.
</p>

<p align="center">
  <img alt="Python" src="https://img.shields.io/badge/Python-3.10+-blue?logo=python&logoColor=white">
  <img alt="License" src="https://img.shields.io/github/license/nim2natty/cyberspace?color=green">
  <img alt="Agents" src="https://img.shields.io/badge/agents-6-a855f7">
  <img alt="Tools" src="https://img.shields.io/badge/tools-41-00d9ff">
  <img alt="Stars" src="https://img.shields.io/github/stars/nim2natty/cyberspace?style=social">
</p>

---

## Swarm Model

`cyberspace swarm` starts the Orchestrator. You describe the objective; it breaks
the work into phases and delegates each phase to a sub-agent with only the tools
needed for that role.

| Agent | Scope | Platform |
|---|---|---|
| Recon | host discovery, DNS, port and service enumeration | AirBender |
| Exploit | web testing, exploit database search, password tools, Metasploit wrappers | ShadowDragon |
| Ghost | browser OPSEC, fingerprint profiles, Tor-aware search status | IceBerg |
| Hardware | ESP32 Marauder, FT232 serial, OpenWrt router control | StickEm |
| Smith | dataset selection, QLoRA planning, training dispatch, local model serving | RoboDaddy |
| Scribe | report synthesis from activity logs | built in |

Supported LLM providers are Ollama, OpenAI, Anthropic, and custom
OpenAI-compatible chat-completions endpoints.

## Quick Start

```bash
cyberspace quickstart

# or step by step
cyberspace setup
cyberspace swarm
```

From source:

```bash
git clone https://github.com/nim2natty/cyberspace
cd cyberspace
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
playwright install chromium
```

Docker:

```bash
docker build -t cyberspace .
docker run -it --rm cyberspace swarm
```

## Platforms

| Platform | Registered capabilities |
|---|---|
| AirBender | `nmap`, `masscan`, ping sweep, WHOIS, `dig`, and chain pipelines such as `recon`, `fast-scan`, and `web-hunt`. |
| ShadowDragon | `sqlmap`, `gobuster`, `whatweb`, `nikto`, `searchsploit`, `john`, `hashcat`, `hydra`, `theharvester`, `impacket-secretsdump`, controlled Kali command execution, and Metasploit search/run wrappers. |
| IceBerg | anti-detect Chromium launch, system OPSEC check, fingerprint profile generation, secure search, and Tor SOCKS status checks. |
| StickEm | ESP32 Marauder command access, nearby AP scans, lab-scoped deauth/PMKID commands, serial port listing, and OpenWrt status/DHCP queries. |
| RoboDaddy | Hugging Face dataset recommendations with license/access notes, QLoRA plan generation, dry-run training, live Vast.ai offer search, Vast.ai training dispatch, `progress.jsonl` job tracking, model registry, and local Ollama Modelfile generation. |

## RoboDaddy

RoboDaddy maps a model request to dataset candidates, a base model, a QLoRA
training plan, GPU cost estimates, and generated job files. It supports dry-run
jobs offline and paid Vast.ai dispatch when you provide a selected offer id.

Browse datasets from a model request:

```bash
cyberspace robodaddy datasets "build a code-review model"
cyberspace robodaddy datasets "authorized red-team assistant"
```

Build a plan:

```bash
cyberspace robodaddy plan "defensive SOC analyst"
```

Run one or more dry-run training jobs at the same time:

```bash
cyberspace robodaddy train offensive_pentest code --provider dry-run
```

Search live Vast.ai offers:

```bash
cyberspace robodaddy instances --gpu RTX_4090 --limit 10
```

Dispatch paid Vast.ai training. Batch paid runs require one `--offer` per model:

```bash
cyberspace robodaddy train offensive_pentest --provider vastai --offer 123456
cyberspace robodaddy train offensive_pentest code --provider vastai --offer 123456 --offer 789012
```

Every job writes generated files under `~/.cyberspace/modules/robodaddy/jobs/<job>/`.
Training progress is appended to `progress.jsonl`; run
`tail -f ~/.cyberspace/modules/robodaddy/jobs/<job>/progress.jsonl` to watch a
job locally. Dataset recommendations include license, row schema, and access
requirements. Gated Hugging Face datasets require accepting their terms and
setting `HF_TOKEN` before a real training run. Vast.ai dispatch records the
console URL and instance id when Vast.ai returns one.

Local serving writes an Ollama Modelfile and API-key record:

```bash
cyberspace robodaddy serve <model-name> --target ollama
cyberspace robodaddy use <model-name>
```

Cloud serving is not provisioned by RoboDaddy yet. Vast.ai support currently
covers offer search and training dispatch.

## Features

- Activity memory in `~/.cyberspace/memory/`, including recent actions and operator profile facts.
- Platform chain pipelines for common recon and web-testing workflows.
- LLM provider switching through `cyberspace iceberg model`.
- Markdown report generation with `cyberspace report --out engagement_report.md`.
- Rules of Engagement loading with `cyberspace swarm --roe engagement.md`.

## Project Layout

```text
cyberspace/
├── swarm.py                 # orchestrator and sub-agent routing
├── memory.py                # activity memory and operator profile
├── agent/                   # Ollama/OpenAI/Anthropic/custom provider adapters
├── platforms/
│   ├── airbender/           # reconnaissance tools and pipelines
│   ├── shadowdragon/        # web, credential, exploit-db, Kali, Metasploit wrappers
│   ├── iceberg/             # OPSEC browser, profiles, secure search
│   ├── stickem/             # ESP32, FT232, OpenWrt controls
│   └── robodaddy/           # dataset recommendations and model-training jobs
├── ui/dashboard.py          # terminal dashboard
├── host.py                  # argument-safe host command runner
└── installer/               # install script, Dockerfile, RPi recipe
```

## Authorized Use

Use this project only in labs, training ranges, your own infrastructure, or
systems where you have written permission to test. Wireless and hardware
commands should target equipment you own or are explicitly authorized to assess.

## License

MIT. See [LICENSE](LICENSE).
