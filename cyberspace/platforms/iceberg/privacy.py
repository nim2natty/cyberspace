"""Passive, cross-platform privacy posture checks and explicit privacy controls."""
from __future__ import annotations

import platform
import re
import socket
from dataclasses import dataclass, asdict

from ...host import is_available, run


@dataclass(frozen=True)
class Finding:
    severity: str
    area: str
    title: str
    evidence: str
    solution: str

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


def _output(name: str, args: list[str], timeout: int = 20) -> str:
    result = run(name, args, timeout=timeout)
    return result.stdout.strip() if result.ok else ""


def mullvad_status() -> str:
    if not is_available("mullvad"):
        return ("Mullvad VPN is not installed. Install the official app from "
                "https://mullvad.net/download/vpn and rerun this command.")
    result = run("mullvad", ["status", "-v"], timeout=20)
    if not result.ok:  # Older CLI releases do not support -v.
        result = run("mullvad", ["status"], timeout=20)
    return result.text()


def mullvad_action(action: str) -> str:
    commands = {
        "connect": ["connect"],
        "disconnect": ["disconnect"],
        "lockdown-on": ["lockdown-mode", "set", "on"],
        "lockdown-off": ["lockdown-mode", "set", "off"],
        "autoconnect-on": ["auto-connect", "set", "on"],
        "autoconnect-off": ["auto-connect", "set", "off"],
    }
    if action not in commands:
        return f"unsupported Mullvad action: {action}"
    if not is_available("mullvad"):
        return mullvad_status()
    return run("mullvad", commands[action], timeout=30).text()


def mullvad_dns(protect: bool = True) -> str:
    if not is_available("mullvad"):
        return mullvad_status()
    args = (["dns", "set", "default", "--block-ads", "--block-trackers", "--block-malware"]
            if protect else ["dns", "set", "default"])
    return run("mullvad", args, timeout=30).text()


def dns_status() -> str:
    system = platform.system()
    if system == "Darwin":
        raw = _output("scutil", ["--dns"])
        servers = sorted(set(re.findall(r"nameserver\[\d+\]\s*:\s*(\S+)", raw)))
    elif system == "Windows":
        raw = _output("powershell", ["-NoProfile", "-Command",
                      "Get-DnsClientServerAddress | Select-Object -Expand ServerAddresses"])
        servers = sorted(set(line.strip() for line in raw.splitlines() if line.strip()))
    else:
        raw = _output("resolvectl", ["status"]) if is_available("resolvectl") else ""
        if raw:
            servers = sorted(set(re.findall(r"DNS Servers?:\s*([^\n]+)", raw)))
        else:
            try:
                text = __import__("pathlib").Path("/etc/resolv.conf").read_text(errors="ignore")
            except OSError:
                text = ""
            servers = re.findall(r"^nameserver\s+(\S+)", text, re.MULTILINE)
    return "DNS servers: " + (", ".join(servers) if servers else "not detected")


def audit() -> list[Finding]:
    """Return detectable privacy/security weaknesses without changing the host."""
    system = platform.system()
    findings: list[Finding] = []

    vpn = mullvad_status()
    if "connected" not in vpn.lower() or "disconnected" in vpn.lower():
        findings.append(Finding(
            "high", "network", "Mullvad VPN is not connected", vpn.splitlines()[0],
            "Install/sign in to Mullvad, then run `cyberspace iceberg vpn connect`; "
            "enable `vpn lockdown-on` to prevent traffic outside the tunnel."))

    dns = dns_status()
    if any(marker in dns for marker in ("8.8.8.8", "8.8.4.4")):
        findings.append(Finding(
            "medium", "dns", "Google public DNS is configured", dns,
            "When connected to Mullvad run `cyberspace iceberg dns protect`, or configure "
            "an encrypted no-log DNS provider in your operating system."))
    elif "not detected" in dns:
        findings.append(Finding(
            "info", "dns", "DNS privacy could not be verified", dns,
            "Inspect the active adapter and enable encrypted DNS; Mullvad users can run "
            "`cyberspace iceberg dns protect`."))

    if system == "Darwin":
        fw = _output("defaults", ["read", "/Library/Preferences/com.apple.alf", "globalstate"])
        if fw.strip() not in ("1", "2"):
            findings.append(Finding("high", "firewall", "macOS firewall is disabled",
                                    "globalstate=" + (fw or "not detected"),
                                    "Open System Settings → Network → Firewall and turn it on."))
        enc = _output("fdesetup", ["status"])
        if "filevault is on" not in enc.lower():
            findings.append(Finding("high", "storage", "FileVault disk encryption is off",
                                    enc or "not enabled",
                                    "Open System Settings → Privacy & Security → FileVault and enable it."))
        updates = _output("softwareupdate", ["--list"], timeout=90)
        if "* Label:" in updates:
            findings.append(Finding("medium", "updates", "macOS updates are available",
                                    "softwareupdate reports pending updates",
                                    "Install reviewed updates in System Settings → General → Software Update."))
    elif system == "Windows":
        fw = _output("powershell", ["-NoProfile", "-Command",
                     "(Get-NetFirewallProfile | Where-Object Enabled -eq $false).Name"])
        if fw:
            findings.append(Finding("high", "firewall", "A Windows firewall profile is disabled", fw,
                                    "Enable every profile in Windows Security → Firewall & network protection."))
        enc = _output("manage-bde", ["-status"])
        if enc and "percentage encrypted: 100%" not in enc.lower():
            findings.append(Finding("high", "storage", "BitLocker is not fully enabled",
                                    "system volume is not reported 100% encrypted",
                                    "Enable Device Encryption/BitLocker and securely back up the recovery key."))
    else:
        firewall_active = ((is_available("ufw") and "active" in _output("ufw", ["status"]).lower()) or
                           (is_available("firewall-cmd") and
                            _output("firewall-cmd", ["--state"]).strip() == "running"))
        if not firewall_active:
            findings.append(Finding("high", "firewall", "No active supported firewall detected",
                                    "ufw/firewalld inactive or unavailable",
                                    "Enable your distribution firewall (for example `sudo ufw enable`) after "
                                    "confirming required inbound services."))
        root_source = _output("findmnt", ["-no", "SOURCE", "/"])
        if root_source and not any(x in root_source for x in ("mapper", "crypt", "dm-")):
            findings.append(Finding("high", "storage", "Root disk encryption was not detected",
                                    root_source,
                                    "Back up the device and enable full-disk encryption (LUKS) during a reviewed "
                                    "distribution installation or migration."))
        if is_available("apt-get"):
            pending = _output("apt-get", ["-s", "upgrade"], timeout=90)
            count = len(re.findall(r"^Inst ", pending, re.MULTILINE))
            if count:
                findings.append(Finding("medium", "updates", f"{count} package updates are available",
                                        "apt simulation reports pending packages",
                                        "Review and install updates with your distribution's supported updater."))

    if socket.gethostname().lower() not in ("localhost", "localhost.localdomain"):
        findings.append(Finding("low", "identity", "Hostname may identify this device",
                                socket.gethostname(),
                                "Use a generic hostname if your network policy permits it; avoid personal names."))
    if not findings:
        findings.append(Finding("info", "audit", "No tested weakness detected",
                                "All supported passive checks passed",
                                "Keep the OS and applications updated and rerun this audit regularly."))
    return findings


def audit_text() -> str:
    findings = audit()
    lines = [f"Iceberg privacy audit: {len(findings)} finding(s)"]
    for finding in findings:
        lines.extend((f"\n[{finding.severity.upper()}] {finding.area}: {finding.title}",
                      f"  evidence: {finding.evidence}", f"  solution: {finding.solution}"))
    lines.append("\nScope: passive supported checks only; this is not a guarantee that every vulnerability was found.")
    return "\n".join(lines)