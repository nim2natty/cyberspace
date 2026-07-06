"""cyberspace - an open-source agentic pentest platform.

A modular, agent-first platform layered on top of Kali Linux for learning and
practicing penetration testing. The cyberbot agent (any LLM of your choice)
orchestrates a set of platforms that wrap real offensive-security tooling:

    IceBerg       OPSEC browser + system opsec layer
    AirBender     networking toolkit (nmap, masscan, aircrack-ng...)
    ShadowDragon  all other Kali tools (web, exploit, creds, recon, post-exploit)
    StickEm       ESP32 Marauder + FT232 hardware bridge
    cyberspace   unified dashboard / one-AI control plane

NOTE: this platform is only fully functional when layered over Kali Linux
(it orchestrates Kali's installed tools). It runs on Kali installs, the Kali
Docker image, and a Kali-based Raspberry Pi 5 image.

Intended for LEGAL security education and lab practice (CompTIA PenTest+,
OSCP study, authorized engagements). Use only against systems you own or are
explicitly authorized to test.
"""

__version__ = "0.5.0"
