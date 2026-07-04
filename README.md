# 🥷 cyberspace

** democratize ai **

cyberspace turns any raspbery pi/linux machine into a
single, friendly command center for practicing penetration testing. Use an API 
key - or train your own LLM, to create your own **personal AI agent**, with memory.
Everything is driven from one CLI, with visuals and guided steps so people new to 
the field can get productive fast.

> ⚖️ **For legal security education and authorized assessments only.** Practice
> against your own lab, or systems you have written permission to test.

## ✨ What's inside

| Platform | Emoji | What it does |
|---|:--:|---|
| **cyberbot agent** | 🧠 | Your pentest AI buddy — local Ollama, OpenAI, Anthropic, or any custom endpoint. **Configure it first** — it powers every other platform. |
| **IceBerg** | 🧊 | OPSEC browser + system opsec + **:: secure** AI searches darkweb. Clearnet seaches leave no fingerprint. Customize fingerprints, DoH, proxy, WebRTC leak prevention, canvas/WebGL/audio spoofing, MAC rotation. |
| **AirBender** | 📶 | Networking toolkit: Merger nmap, masscan, host discovery — cross functionality utilized by AI. |
| **ShadowDragon** | 🐍 | Kali's interface: metaploit, sqlmap, gobuster, whatweb (web/recon/exploit). - cross-functional AI |
| **StickEm** | 🔌 | ESP32 Marauder + FT232 + Router merged into one hardware bridge (wireless + serial console + router). |
| **TrainABaby** | 👶 | Give your baby a purpose: pick a use case + public dataset + cloud GPU, fine-tune, serve it behind an API key, and plug it back into cyberbot.|
| **cyberspace** | 🎛️ | Dashboard - view/access every tool, or command them all from **one AI**. |

```
                         ┌─────────────────────────┐
                         │   cyberspace dashboard  │  <- cyberspace dashboard
                         │   (one AI, all tools)    │
                         └────────────┬─────────────┘
                                      │
        ┌─────────────────────────────┼─────────────────────────────┐
        ▼                ▼            ▼                ▼             ▼
   🧠 cyberbot      🧊 IceBerg   📶 AirBender   🐍 ShadowDragon  🔌 StickEm
   agent core        OPSEC        networking     web/exploit       ESP32+FT232
        │
   Ollama / OpenAI / Anthropic / custom LLM   <- configure FIRST (cyberspace setup)
```

## 🚀 Install

**A — one command (Linux / macOS):**
```bash
curl -fsSL https://raw.githubusercontent.com/nim2natty/cyberspace/main/installer/install.sh | bash
```
**B — Docker (Mac / Linux / Windows):**
```bash
docker build -t cyberspace .
docker run -it --rm cyberspace            # dashboard
# expose serial hardware: --device /dev/ttyUSB0
```
**C — Flash a Raspberry Pi 5 image:** see [`installer/rpi-build/README.md`](installer/rpi-build/README.md) (pi-gen recipe).
**D — From source:**
```bash
git clone https://github.com/nim2natty/cyberspace && cd cyberspace
python3 -m venv .venv && source .venv/bin/activate
pip install -e . && playwright install chromium
```

## 🧠 Step 1 (important): configure the agent FIRST

Every platform's agentic features plug into the **cyberbot agent**, so set it
up before anything else. Once configured, the agent automatically gains control
of every tool you install afterward.

```bash
cyberspace setup      # guided wizard: ollama | openai | anthropic | custom
cyberspace doctor     # confirm everything is ready
```

## 🧰 Step 2: use it

```bash
# Talk to the agent — it calls any tool across all platforms:
cyberspace agent
# e.g. "Scan my lab 10.10.10.0/24, identify the web app, then browse it with IceBerg."

# Or run a platform directly:
cyberspace iceberg profile new win --persona win-chrome
cyberspace iceberg browse -p win --selftest      # verify spoofing offline
cyberspace iceberg secure status                       # :: secure AI find - check Tor + deps
cyberspace iceberg secure config                       # set brightside/darkside posture FIRST
cyberspace iceberg secure find "ransomware ACME leak" --mode dark   # AI find via Tor
cyberspace iceberg secure gui                          # graphic interface (Streamlit)
cyberspace airbender nmap 10.10.10.5
cyberspace shadowdragon whatweb http://10.10.10.5

# Or see everything in one place:
cyberspace dashboard                              # cyberspace
```

## 🧊 IceBerg :: secure  — AI-powered find & browse (brightside / darkside)

A feature of IceBerg that turns the platform into a **customizable, secure,
all-in-one AI browsing experience**. It adapts the open-source
[Robin](https://github.com/apurvsinghgautam/robin) dark-web OSINT engine (MIT,
© apurvsinghgautam) so the **same cyberbot LLM** you configured in Step 1
refines a query, searches, filters, scrapes, and writes a structured summary.

Two modes:
- **brightside** — clearnet search + AI find (no Tor). DoH on, WebRTC blocked.
- **darkside** — full internet via **Tor**: searches 16 onion engines over
  SOCKS5h, with a different security posture (new identity per run, DoH, WebRTC
  lockdown, TLS verification relaxed for self-signed onion certs).

> ⚖️ Set your security configuration **before** darkside browsing
> (`cyberspace iceberg secure config`). Dark mode changes your transport, DNS, and
> WebRTC posture — the wizard makes you confirm each.

```bash
cyberspace iceberg secure config            # interactive posture wizard (do this first)
cyberspace iceberg secure status            # Tor reachable? deps installed?
cyberspace iceberg secure find "<query>" --mode dark --preset threat_intel
cyberspace iceberg secure browse http://example.onion --mode dark   # torified browser
cyberspace iceberg secure gui               # graphic interface at localhost:8501
```

Presets: `general`, `threat_intel`, `personal_identity`, `corporate_espionage`.
The agent can call it too: ask cyberbot *"find leaked credentials for ACME on the
dark web"* and it invokes `iceberg.secure_find` across all your tools.

## 👶 TrainABaby — train your own personalized AI model

TrainABaby closes the loop: **train a custom model → serve it → plug it back into
cyberbot as its brain.** Describe what you want your AI to do, pick a public
training dataset + base model + GPU, fine-tune for N days, then deploy it behind an
OpenAI-compatible API key any agent can use.

```bash
# browse what's possible
cyberspace trainababy usecases                      # offensive, defensive, assistant, ...
cyberspace trainababy datasets -u offensive_pentest  # public HF datasets
cyberspace trainababy gpus                           # what each GPU can train
cyberspace trainababy providers                      # Vast.ai, RunPod, Lambda, local

# search LIVE cloud GPU offers (real prices, no key needed to browse)
cyberspace trainababy instances --gpu RTX_4090

# plan + train
cyberspace trainababy plan "offensive pen security"  # interactive cost estimate
cyberspace trainababy train offensive_pentest --base llama3.1-8b --gpu RTX_4090 --days 2

# serve + use
cyberspace trainababy jobs                           # training statistics (loss, $, hours)
cyberspace trainababy models                         # trained model registry
cyberspace trainababy serve llama3.1-8b-offensive_pentest-d2 --target ollama
cyberspace trainababy keys                           # API keys for served models
cyberspace trainababy use llama3.1-8b-offensive_pentest-d2   # cyberbot now runs YOUR model
```

**Model switching** (new in IceBerg): switch the active LLM without re-running setup:
```bash
cyberspace iceberg model list                 # current model + what's installed
cyberspace iceberg model switch qwen2.5-coder:7b
cyberspace iceberg model provider openai --api-key sk-...
```

## 🔌 Step 3: connect your hardware

cyberspace drives real gear in a lab. After `cyberspace setup`:

```bash
cyberspace stickem ports                 # find your ESP32 + FT232
cyberspace stickem set-esp32 /dev/ttyUSB0
cyberspace stickem set-ft232  /dev/ttyUSB1
cyberspace stickem marauder scanap        # drive Marauder directly
cyberspace stickem console                # raw serial console (router/IoT UART)
```

Then just ask the agent in plain English:
> *"Scan for access points, select my LabNet SSID, and capture a handshake."*

> **Scope:** 2.4GHz deauth/rogue-AP and serial UART are for **your own** lab
> AP/router/IoT devices. Wireless emissions can't be contained to a cable, so
> never target networks or spectrum you don't own.

## 🗂️ Project layout

```
cyberspace/
├── cyberspace/
│   ├── cli.py                 # main CLI (setup/agent/dashboard/doctor/...)
│   ├── agent/                 # LLM-agnostic agent (ollama/openai/anthropic/custom)
│   │   ├── core.py            #   tool-calling loop
│   │   ├── llm.py             #   provider abstraction
│   │   └── setup.py           #   first-run wizard
│   ├── modules/               # plugin system (base + auto-discovery)
│   ├── platforms/             # built-in platforms:
│   │   ├── iceberg/           #   🧊 OPSEC browser + system opsec
│   │   ├── airbender/         #   📶 networking toolkit
│   │   ├── shadowdragon/      #   🐍 web/recon/exploit toolkit
│   │   └── stickem/         #   🔌 ESP32 + FT232 bridge
│   ├── ui/dashboard.py        # 🎛️ cyberspace
│   └── host.py                # safe host-tool runner
├── installer/                 # install.sh + Dockerfile + pi-gen recipe
└── tests/
```

**Adding a platform (third-party friendly):** ship a package named
`cyberspace_module_<name>` exposing a `MODULE` (`cyberspace.modules.base.Module`
subclass). It's auto-discovered and gets its own CLI subcommand + agent tools.

## 🎓 Why it's great for CompTIA PenTest+

Every domain maps to a platform: Info Gathering (AirBender), Vulnerability ID &
Exploits (ShadowDragon), Wireless/IoT (StickEm), OPSEC (IceBerg), Reporting
(the agent writes up findings). The agent-first design also teaches the modern
**agentic offensive workflow** (PentestGPT/CAI-style) — a genuine career edge.

## ⚠️ Limitations (honest)

- **TLS/JA3 fingerprint** is set by the browser stack; IceBerg mitigates (common
  Chromium JA3 + VPN + DoH) but can't fully customize it via JS injection.
- Agent loops are bounded; very long engagements need chunking.
- StickEm hardware attacks are 2.4GHz / serial only and lab-scoped.

## 🤝 Contributing

PRs welcome. Needs love: more ShadowDragon wrappers (metasploit, bloodhound,
netexec), a richer Textual dashboard, and `.deb`/AUR packages.

## License

MIT — see [LICENSE](LICENSE).

