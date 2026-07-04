# 🥷 cyberspace

**An open-source, agent-first penetration-testing platform — for learners and pros.**

cyberspace turns a Raspberry Pi 5 (or any Linux/macOS/Windows machine) into a
single, friendly command center for practicing penetration testing. A
**personal AI agent** (any LLM you choose) orchestrates a set of platforms that
wrap real offensive-security tooling. Everything is driven from one CLI, with
visuals and guided steps so people new to pentest can get productive fast.

> ⚖️ **For legal security education and authorized assessments only.** Practice
> against your own lab (DVWA, Juice Shop, GOAD, your own router/AP) or systems
> you have written permission to test.

> ℹ️ **About the name:** "cyberspace" is used here for an open-source cybersecurity
> software project. "Cyberpunk 2077" is a trademark of CD Projekt Red for
> entertainment; this project is unrelated software in a different field.

## ✨ What's inside

| Platform | Emoji | What it does |
|---|:--:|---|
| **Cyberbot agent** | 🧠 | Your personal pentest AI — local Ollama, OpenAI, Anthropic, or any custom endpoint. **Configure it first** — it powers every other platform. |
| **IceBerg** | 🧊 | OPSEC browser + system opsec: custom fingerprints, DoH, proxy, WebRTC leak prevention, canvas/WebGL/audio spoofing, MAC rotation. |
| **AirBender** | 📶 | Networking toolkit: nmap, masscan, host discovery — agent-driven. |
| **ShadowDragon** | 🐍 | Everything else: sqlmap, gobuster, whatweb (web/recon/exploit). |
| **StickEm** | 🔌 | ESP32 Marauder + FT232 merged into one hardware bridge (wireless + serial console). |
| **CyberPunked** | 🎛️ | The unified dashboard — view/access every tool, or command them all from **one AI**. |

```
                         ┌─────────────────────────┐
                         │   CyberPunked dashboard  │  <- cyberspace dashboard
                         │   (one AI, all tools)    │
                         └────────────┬─────────────┘
                                      │
        ┌─────────────────────────────┼─────────────────────────────┐
        ▼                ▼            ▼                ▼             ▼
   🧠 Cyberpunk      🧊 IceBerg   📶 AirBender   🐍 ShadowDragon  🔌 StickEm
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

Every platform's agentic features plug into the **Cyberbot agent**, so set it
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
cyberspace airbender nmap 10.10.10.5
cyberspace shadowdragon whatweb http://10.10.10.5

# Or see everything in one place:
cyberspace dashboard                              # CyberPunked
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
│   ├── ui/dashboard.py        # 🎛️ CyberPunked
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

