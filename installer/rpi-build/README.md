# Raspberry Pi 5 image builder

cyberspace ships as a **flashable Raspberry Pi OS image** built on top of the
official Raspberry Pi OS Lite (64-bit, Bookworm) using [pi-gen][pig]. This is
how you turn an RPi5 into a portable "stickem" appliance: flash, boot, run
`cyberspace setup`, done.

## Quick build (on a Linux/macOS host with Docker)

```bash
# 1) clone pi-gen
git clone https://github.com/RPi-Distro/pi-gen.git
cd pi-gen

# 2) add the cyberspace stage
mkdir -p stages/cyberspace
# copy these files into stages/cyberspace/ (see below)

# 3) build (produces image in deploy/)
PRESERVE_CONTAINER=1 ./build-docker.sh
```

## stages/cyberspace/00-cyberspace/00-run.sh

Installs the platform into the image at build time:

```sh
#!/bin/bash -e
on_chroot <<'EOF'
apt-get update
apt-get install -y python3-pip python3-venv git nmap masscan sqlmap gobuster \
  whatweb macchanger tor proxychains4 seclists aircrack-ng tcpdump
python3 -m pip install --break-system-packages cyberspace
python3 -m playwright install chromium --with-deps
EOF
```

## stages/cyberspace/01-boot-behaviour/00-run.sh

Headless-friendly defaults so the Pi boots straight into the platform on
first power-up (SSH enabled, hostname set, a welcome banner):

```sh
#!/bin/bash -e
# enable ssh
on_chroot <<'EOF'
systemctl enable ssh
hostnamectl set-hostname stickem
EOF
# first-run hint in MOTD
cat > "${ROOTFS_DIR}/etc/motd" <<'EOF'
   ___
  / __|_ __ _ __ ___  _ __  cyberspace is installed.
 | (__ | '_ \ '_ \ _ \| ' \  run: cyberspace setup
  \___|| . | . | (_) | ._|_|      cyberspace doctor
       |_| |_|_|___|\___|         cyberspace dashboard
EOF
```

## stages/cyberspace/01-boot-behaviour/01-packages

```
pi-bluetooth
```

## Flashing the result

After the build, flash `deploy/image_*.img` to a microSD (A2 class, 64GB+):

```bash
# macOS / Linux
xzcat deploy/image_*.img.xz | sudo dd of=/dev/sdX bs=4M status=progress
sync
```

Insert into the RPi5, power on, and from another machine:

```bash
ssh cyberspace@stickem.local
cyberspace setup       # configure the agent first
cyberspace doctor
```

[pig]: https://github.com/RPi-Distro/pi-gen
