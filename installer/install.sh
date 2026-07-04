#!/usr/bin/env bash
# cyberspace installer - provisions the platform on top of Linux/macOS.
#
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/nim2natty/cyberspace/main/installer/install.sh | bash
#   or:  bash installer/install.sh
#
# This turns a stock Kali/Debian/Ubuntu (or macOS) box into a cyberspace host:
#   - installs python deps
#   - installs the recommended offensive + opsec tools (apt / brew)
#   - installs the cyberspace package (editable from a clone, or pip from PyPI)
set -euo pipefail

cyan='\033[0;36m'; green='\033[0;32m'; yellow='\033[1;33m'; red='\033[0;31m'; nc='\033[0m'
say() { printf "${cyan}[cyberspace]${nc} %s\n" "$1"; }
ok()  { printf "${green}[ok]${nc} %s\n" "$1"; }
warn(){ printf "${yellow}[!]${nc} %s\n" "$1"; }
die() { printf "${red}[x]${nc} %s\n" "$1"; exit 1; }

say "Welcome to the cyberspace installer."
say "This script sets up the agentic pentest platform on this machine."

# --- OS detection -----------------------------------------------------------
OS="unknown"; PKGMGR=""
if [[ "$OSTYPE" == "darwin"* ]]; then OS="macos";
elif command -v apt-get >/dev/null 2>&1; then OS="debian"; PKGMGR="apt";
elif command -v dnf >/dev/null 2>&1; then OS="fedora"; PKGMGR="dnf";
else die "unsupported OS ($OSTYPE). See docs for manual install."; fi
ok "detected OS: $OS"

install_pkgs_debian() {
  local pkgs=("$@")
  sudo apt-get update -qq
  for p in "${pkgs[@]}"; do
    if ! dpkg -l "$p" >/dev/null 2>&1; then
      say "installing $p ..."; sudo apt-get install -y "$p" >/dev/null
    fi
  done
}

# --- Core Python deps -------------------------------------------------------
say "checking python3..."
command -v python3 >/dev/null 2>&1 || die "python3 required."

say "installing python deps for cyberspace..."
if [[ "$OS" == "macos" ]]; then
  command -v brew >/dev/null 2>&1 || die "Homebrew required on macOS (https://brew.sh)"
  brew install -q python@3.11 || true
fi

# --- Offensive + opsec tooling ---------------------------------------------
TOOLS_DEB=(python3-pip python3-venv git nmap masscan sqlmap gobuster whatweb
           macchanger tor proxychains-ng seclists)
TOOLS_BREW=(nmap sqlmap masscan)

if [[ "$OS" == "debian" ]]; then
  say "installing offensive tooling via apt (this needs sudo)..."
  install_pkgs_debian "${TOOLS_DEB[@]}" || warn "some apt packages unavailable - continuing"
elif [[ "$OS" == "macos" ]]; then
  say "installing offensive tooling via brew..."
  for p in "${TOOLS_BREW[@]}"; do brew install -q "$p" 2>/dev/null || warn "couldn't install $p via brew"; done
fi
ok "tooling install step complete"

# --- cyberspace package ------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
if [[ -f "$ROOT_DIR/pyproject.toml" ]]; then
  say "detected repo clone - installing cyberspace editable from $ROOT_DIR"
  cd "$ROOT_DIR"
else
  say "no local clone - installing cyberspace from PyPI"
  ROOT_DIR="$(mktemp -d)"; cd "$ROOT_DIR"
  git clone --depth 1 https://github.com/nim2natty/cyberspace . 2>/dev/null || \
    warn "could not clone - install via: pip install cyberspace"
fi

python3 -m venv .venv || die "venv creation failed"
# shellcheck disable=SC1091
source .venv/bin/activate
pip install --upgrade pip -q
pip install -e . -q || die "cyberspace pip install failed"
say "downloading the IceBerg browser engine (chromium)..."
python -m playwright install chromium -q || warn "playwright chromium install needs network"
ok "cyberspace installed"

# --- next steps -------------------------------------------------------------
cat <<EOF

${green}All set.${nc} Next steps:

  1) source venv:       ${cyan}source .venv/bin/activate${nc}
  2) configure agent:   ${cyan}cyberspace setup${nc}        ${yellow}<- do this FIRST${nc}
  3) check everything:  ${cyan}cyberspace doctor${nc}
  4) launch a platform: ${cyan}cyberspace iceberg profile new win --persona win-chrome${nc}
                        ${cyan}cyberspace iceberg browse -p win --selftest${nc}
  5) one AI for all:    ${cyan}cyberspace dashboard${nc}    (CyberPunked)

Docs: https://github.com/nim2natty/cyberspace
EOF
say "Done. Happy (legal) hacking."
