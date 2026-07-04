"""ShadowDragon Kali tool catalog.

Enumerates the non-networking Kali Linux tools ShadowDragon can orchestrate.
Networking/scanning tools (nmap, masscan, aircrack-ng suite...) belong to
AirBender; ShadowDragon covers everything else: web apps, exploitation,
passwords, recon/OSINT, post-exploitation/AD, sniffing & MITM, forensics,
crypto/stego, reverse engineering, and database assessment.

This is a Kali overlay: the catalog lists what CAN be used; `installed()`
checks which are actually present on the host (they ship with Kali).
"""

# category -> list of Kali tool binary names (no networking/scanning tools).
KALI_CATALOG = {
    "web": [
        "sqlmap", "gobuster", "whatweb", "nikto", "ffuf", "wpscan", "dirb",
        "dirbuster", "feroxbuster", "nuclei", "commix", "wafw00f", "httpx",
    ],
    "exploit": [
        "msfconsole", "msfrpcd", "searchsploit", "set", "shellnoob",
    ],
    "password": [
        "john", "hashcat", "hydra", "medusa", "ncrack", "cewl", "crunch",
        "hashid", "hash-identifier", "chntpw",
    ],
    "recon": [
        "theHarvester", "recon-ng", "amass", "sublist3r", "subfinder",
        "sherlock", "dnsenum", "dnsrecon", "fierce",
    ],
    "post_exploit": [
        "bloodhound-python", "crackmapexec", "netexec", "impacket-secretsdump",
        "impacket-psexec", "impacket-wmiexec", "impacket-getTGT", "evil-winrm",
        "mimikatz", "powershell-empire", "starkiller",
    ],
    "sniff_mitm": [
        "bettercap", "responder", "mitm6", "mitmproxy", "tshark", "tcpdump",
        "ettercap", "dsniff", "pcapfix",
    ],
    "forensics": [
        "volatility", "volatility3", "binwalk", "foremost", "sleuthkit",
        "mmls", "fls", "icat", "scalpel", "hashdeep",
    ],
    "crypto_stego": [
        "openssl", "steghide", "stegseek", "stegcracker", "outguess", "hashid",
    ],
    "reverse": [
        "radare2", "r2", "gdb", "ghidra", "objdump", "strings", "ltrace",
        "strace", "lief",
    ],
    "db": [
        "sqlmap", "mdb-tables", "mdb-sql", "sqlsus", "bbqsql", "sqsh",
    ],
}


def all_tools() -> list[str]:
    """Unique list of every catalog tool name."""
    seen: list[str] = []
    for tools in KALI_CATALOG.values():
        for t in tools:
            if t not in seen:
                seen.append(t)
    return seen
