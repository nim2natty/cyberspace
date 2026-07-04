"""StickEm serial bridge - merges ESP32 Marauder + FT232 control.

Marauder (on the ESP32) speaks a text CLI over UART (115200 8N1). The FT232 is
a USB-UART bridge. This module gives one clean Python interface to BOTH:
  - Marauder commands (scanap, attack -t deauth, sniffpmkid, ...) over a serial port
  - raw serial console access for any other UART target (routers, IoT devices)

Used against your OWN lab gear only. Deauth/rogue-AP attacks are 2.4 GHz and
must target SSIDs you own - that's the legal, exam-relevant use.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class SerialTarget:
    port: str          # e.g. /dev/ttyUSB0 (FT232) or /dev/ttyACM0 (ESP32 native USB)
    baudrate: int = 115200
    label: str = ""    # "esp32-marauder" | "ft232-console" | "openwrt-uart"
    timeout: float = 5.0


def _open(target: SerialTarget):
    try:
        import serial  # pyserial
    except ImportError as e:
        raise RuntimeError("pyserial not installed: pip install pyserial") from e
    return serial.Serial(target.port, target.baudrate, timeout=target.timeout)


class MarauderBridge:
    """Drive an ESP32 running Marauder over its serial CLI."""

    def __init__(self, port: str, baudrate: int = 115200, label: str = "esp32-marauder"):
        self.target = SerialTarget(port=port, baudrate=baudrate, label=label)

    def send(self, command: str, wait: float = 4.0, read_bytes: int = 8000) -> str:
        """Send a Marauder command and return the text response."""
        ser = _open(self.target)
        try:
            ser.reset_input_buffer()
            ser.write((command.strip() + "\n").encode())
            ser.flush()
            import time
            time.sleep(wait)
            return ser.read(read_bytes).decode(errors="replace")
        finally:
            ser.close()

    def help(self) -> str:
        return self.send("help", wait=2.0)

    def scan_ap(self) -> str:
        return self.send("scanap", wait=6.0)

    def list_targets(self) -> str:
        return self.send("list -a", wait=2.0)

    def select_ssid(self, ssid: str) -> str:
        return self.send(f"select -n {ssid}", wait=1.5)

    def deauth(self, count: int = 50) -> str:
        return self.send(f"attack -t deauth -c {count}", wait=8.0)

    def sniff_pmkid(self) -> str:
        return self.send("sniffpmkid", wait=10.0)


class ConsoleBridge:
    """Raw serial console for any UART target via the FT232 (routers, IoT, etc.).

    Interactive use: open_console() reads stdin and writes to the port.
    """

    def __init__(self, port: str, baudrate: int = 115200, label: str = "ft232-console"):
        self.target = SerialTarget(port=port, baudrate=baudrate, label=label)

    def write_read(self, data: str, wait: float = 2.0) -> str:
        ser = _open(self.target)
        try:
            ser.write(data.encode())
            ser.flush()
            import time
            time.sleep(wait)
            return ser.read(4000).decode(errors="replace")
        finally:
            ser.close()

    def open_console(self) -> None:
        """Minimal interactive console. Ctrl-C to exit."""
        import sys
        ser = _open(self.target)
        print(f"[console] {self.target.label} @ {self.target.port} "
              f"({self.target.baudrate}). Ctrl-C to exit.")
        try:
            import threading
            stop = threading.Event()

            def reader():
                while not stop.is_set():
                    if ser.in_waiting:
                        sys.stdout.write(ser.read(ser.in_waiting).decode(errors="replace"))
                        sys.stdout.flush()

            t = threading.Thread(target=reader, daemon=True)
            t.start()
            while not stop.is_set():
                line = sys.stdin.readline()
                if not line:
                    break
                ser.write(line.encode())
                ser.flush()
        except KeyboardInterrupt:
            pass
        finally:
            ser.close()
            print("\n[console] closed.")


def list_ports() -> list[str]:
    """List available serial ports (helps the user pick the ESP32 / FT232)."""
    try:
        from serial.tools import list_ports
        return [p.device for p in list_ports.comports()]
    except Exception:
        return []
