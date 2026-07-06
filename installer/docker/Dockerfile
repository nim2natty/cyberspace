# cyberspace Docker image - runs on any host with Docker (macOS/Linux/Windows).
# A self-contained pentest + agentic platform you can `docker run` anywhere.
#
#   docker build -t cyberspace .
#   docker run -it --rm cyberspace            # start the dashboard
#   docker run -it --rm cyberspace setup      # configure the agent
#
# NOTE: GUI browser (IceBerg) and raw-socket wireless attacks need extra flags:
#   - IceBerg headless works out of the box; for a visible browser add
#     `-e DISPLAY -v /tmp/.X11-unix:/tmp/.X11-unix` (Linux host)
#   - StickEm serial: add `--device /dev/ttyUSB0` to expose the ESP32/FT232
FROM kalilinux/kali-rolling:latest

LABEL org.opencontainers.image.title="cyberspace" \
      org.opencontainers.image.description="Agentic security lab platform with scoped tool agents" \
      org.opencontainers.image.source="https://github.com/nim2natty/cyberspace"

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Selected Kali tools used by the built-in platform wrappers, plus Python and OPSEC utilities.
RUN apt-get update && apt-get install -y --no-install-recommends \
      python3 python3-pip python3-venv git curl ca-certificates \
      nmap masscan sqlmap gobuster whatweb \
      macchanger tor proxychains4 seclists wordlists \
      aircrack-ng wireshark-common tcpdump \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /opt/cyberspace
COPY . /opt/cyberspace

RUN python3 -m pip install --break-system-packages --upgrade pip \
    && python3 -m pip install --break-system-packages -e . \
    && python3 -m playwright install chromium --with-deps \
    && rm -rf /root/.cache/pip

# Persistent state lives here (agent config, profiles, logs).
ENV CYBERSPACE_HOME=/data
VOLUME ["/data"]

ENTRYPOINT ["cyberspace"]
CMD ["dashboard"]
