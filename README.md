<p align="center">
  <img src=".github/banner.svg" width="640" alt="cyberspace">
</p>

<p align="center">
  <img alt="Python" src="https://img.shields.io/badge/Python-3.10+-blue?logo=python&logoColor=white">
  <img alt="License" src="https://img.shields.io/github/license/nim2natty/cyberspace?color=green">
  <img alt="Stars" src="https://img.shields.io/github/stars/nim2natty/cyberspace?style=social">
</p>

---

## What is cyberspace?

**cyberspace is the brain for your cyberdeck.**

A cyberdeck is a portable, custom-built hacking computer. cyberspace is the
software that runs on it — an AI assistant that talks to you in plain English and
does the work of an entire security team.

You tell it what you want to do (for example: *"scan my home network and tell me
what's vulnerable"*). It figures out which tools to use, runs them, and explains
the results in a way you can understand — even if you're not a security expert.

> **Built for:** the cyberdeck you're manufacturing. It runs on a Raspberry Pi 5,
> a laptop, or anything that runs Linux, macOS, or Windows.

## How it works

Behind the scenes, cyberspace is a **team of AI agents** — think of them as
digital coworkers, each with a different job:

| Agent | Job (in plain English) |
|---|---|
| **Recon** 📶 | The scout. Maps out a network — finds every device, what ports are open, what software is running. |
| **Exploit** 🐍 | The tester. Tries to break into things you've found, using tools like Metasploit (a famous hacking toolkit). |
| **Ghost** 🧊 | The spy. Keeps you anonymous (a special browser that hides your identity) and searches the dark web for information. |
| **Hardware** 🔌 | The hands. Controls physical gear — a WiFi attack board (ESP32), a serial cable (FT232), and your OpenWrt router. |
| **Smith** 🤖 | The engineer. Builds custom AI models — you describe what you want the AI to be good at, and it trains one. |
| **Scribe** 📝 | The writer. Takes everything the team found and writes a clear report. |

You don't talk to each agent individually. You talk to the **Orchestrator** — the
team lead. You give it a goal, and it hands out the work.

```
       you  →  ORCHESTRATOR  →  [ Recon → Exploit → Scribe → ... ]
```

## Getting started

**One command** gets you going:

```bash
cyberspace quickstart
```

This asks you to pick an AI model (the "brain" — you can use a free local one like
Ollama, or a paid cloud one like OpenAI), then drops you into the swarm.

**Or step by step:**

```bash
cyberspace setup      # choose your AI model
cyberspace swarm      # start the team
```

<details>
<summary><b>Install on a cyberdeck / Raspberry Pi / from source</b></summary>

```bash
# From source (on the cyberdeck)
git clone https://github.com/nim2natty/cyberspace && cd cyberspace
python3 -m venv .venv && source .venv/bin/activate
pip install -e . && playwright install chromium

# Docker (anywhere)
docker build -t cyberspace .
docker run -it --rm cyberspace swarm

# Flash a Raspberry Pi 5 image (see installer/rpi-build/)
```
</details>

## What can it actually do?

Here are real examples of what you can ask the team to do:

**"Scan my home network and tell me what's exposed."**
→ Recon discovers every device, checks which ports are open, and lists what
software each one is running.

**"Test my web app for vulnerabilities."**
→ Exploit runs a chain of tools: identifies the technology (`whatweb`), scans for
weaknesses (`nikto`), searches for known exploits (`searchsploit`), and can launch
Metasploit attacks if you approve.

**"Search the dark web for mentions of my company."**
→ Ghost connects through Tor (the anonymity network), searches 16 dark-web search
engines, filters the results with AI, and writes a summary.

**"Control my lab router and WiFi board."**
→ Hardware connects to your OpenWrt router over SSH and your ESP32 board over
serial — scans for WiFi networks, can capture handshakes, reads router config.

**"Build me an AI that specializes in code review."**
→ Smith picks a public training dataset, plans the GPU rental on Vast.ai (a cloud
GPU marketplace), generates the training script, and serves the finished model
back as the team's new brain.

## The pieces

cyberspace is made of five **platforms**. Each one is a set of real security tools
wrapped so the AI can use them — and so you can use them directly from the
command line:

| Platform | What it is | Example tools |
|---|---|---|
| **AirBender** 📶 | Network scanner — finds devices and services on a network | nmap, masscan, dig |
| **ShadowDragon** 🐍 | Web and exploit toolkit — tests for and breaks into vulnerabilities | sqlmap, Metasploit, hydra |
| **IceBerg** 🧊 | Privacy browser — hides who you are; searches the clear and dark web | Tor, anti-detect Chromium |
| **StickEm** 🔌 | Hardware controller — drives your WiFi board, serial cable, and router | ESP32 Marauder, FT232, OpenWrt |
| **RoboDaddy** 🤖 | AI trainer — builds custom AI models on rented cloud GPUs | Hugging Face datasets, Vast.ai |

### Chain commands (tools that work together)

Instead of running each tool one at a time, you can run a whole sequence with one
command. Each tool's output feeds into the next:

```bash
cyberspace airbender recon 192.168.1.0/24
# runs: find devices → scan their ports → identify services

cyberspace shadowdragon full-assault http://10.10.10.5
# runs: identify tech → find hidden pages → scan for vulns → search exploits → attack
```

### It remembers you

cyberspace keeps a memory of what you've done — your favorite tools, the networks
you test, your skill level. Over time it needs fewer instructions because it
already knows your habits.

```bash
cyberspace memory show    # see what it knows about you
```

## Legal use

For authorized security testing and education only. Use it on your own network,
your own devices, your own lab — or systems you have written permission to test.
Wireless and Tor features should only target equipment and networks you own.

## License

MIT — see [LICENSE](LICENSE).

