"""IceBerg browser + DoH (ported & condensed from veil).

Launches a fully spoofed, sealed Chromium with DoH-only DNS, WebRTC leak
prevention, canvas/WebGL/audio noise, ClientHints, and live query visibility.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Optional

import httpx
from rich.console import Console
from rich.panel import Panel

SPOOF_JS = Path(__file__).resolve().parent / "spoof" / "inject.js"
SELFTEST = Path(__file__).resolve().parent / "data" / "selftest.html"

DOH_PROVIDERS = {
    "mullvad": "https://doh.mullvad.net/dns-query",
    "cloudflare": "https://cloudflare-dns.com/dns-query",
    "quad9": "https://dns.quad9.net:5053/dns-query",
    "google": "https://dns.google/resolve",
}
SEARCH_ENGINES = {
    "duckduckgo.com": "q", "www.google.com": "q", "google.com": "q",
    "search.brave.com": "q", "www.bing.com": "q", "lite.duckduckgo.com": "q",
    "startpage.com": "query",
}


def install_engine() -> tuple[bool, str]:
    """Download Playwright's matching Chromium build for this user."""
    import subprocess
    try:
        from playwright._impl._driver import compute_driver_executable, get_driver_env
        node, cli = compute_driver_executable()
        proc = subprocess.run([node, cli, "install", "chromium"], text=True,
                              capture_output=True, env=get_driver_env(), timeout=900)
        output = (proc.stdout or proc.stderr).strip()
        return proc.returncode == 0, output or ("Chromium installed" if proc.returncode == 0 else "install failed")
    except Exception as exc:
        return False, f"could not install Chromium: {exc}"


class DoH:
    def __init__(self, provider: str = "mullvad"):
        self.endpoint = DOH_PROVIDERS.get(provider, DOH_PROVIDERS["mullvad"])

    def resolve(self, name: str) -> list[str]:
        try:
            r = httpx.get(self.endpoint, params={"name": name, "type": "A"},
                          headers={"accept": "application/dns-json"}, timeout=5.0)
            return [a.get("data", "") for a in r.json().get("Answer", [])]
        except Exception:
            return []

    def chromium_args(self) -> list[str]:
        return ["--enable-features=DnsOverHttps", "--dns-over-https-mode=secure",
                f"--dns-over-https-templates={self.endpoint}"]


def _spoof_config(p) -> dict:
    return {k: getattr(p, k) for k in (
        "user_agent platform locale languages hardware_concurrency device_memory "
        "max_touch_points screen_width screen_height color_depth device_pixel_ratio "
        "timezone webgl_vendor webgl_renderer noise_seed webrtc_mode block_tracking "
        "canvas_noise audio_noise architecture bitness platform_version sec_ch_ua "
        "sec_ch_ua_mobile sec_ch_ua_platform ua_full_version_list".split())}


def _headers(p) -> dict:
    h = {"Accept-Language": ",".join(p.languages)}
    if p.sec_ch_ua:
        h["sec-ch-ua"] = p.sec_ch_ua
        h["sec-ch-ua-mobile"] = p.sec_ch_ua_mobile
        h["sec-ch-ua-platform"] = p.sec_ch_ua_platform
    return h


def _proxy_dict(url: str) -> dict:
    from urllib.parse import urlparse
    pp = urlparse(url)
    d = {"server": f"{pp.scheme}://{pp.hostname}:{pp.port}"}
    if pp.username:
        d["username"] = pp.username
    if pp.password:
        d["password"] = pp.password
    return d


def launch(profile, url: Optional[str] = None, headless: bool = False,
           selftest: bool = False, console: Optional[Console] = None) -> None:
    from playwright.sync_api import sync_playwright
    console = console or Console()
    doh = DoH(profile.doh_provider)
    session = datetime.now().strftime("%Y%m%d-%H%M%S")
    seen: set[str] = set()

    def on_nav(frame):
        if frame != page.main_frame:
            return
        u = frame.url
        if not u or u.startswith(("about:", "data:", "blob:", "chrome:", "devtools:")):
            return
        from urllib.parse import urlparse, parse_qs
        host = urlparse(u).hostname or ""
        if not host:
            return
        if host not in seen:
            seen.add(host)
            ips = ",".join(doh.resolve(host)) or "(cached/blocked)"
            console.print(f"[cyan]dns[/cyan]  {host}  -> {ips}")
        for eh, param in SEARCH_ENGINES.items():
            if host == eh or host.endswith("." + eh):
                q = parse_qs(urlparse(u).query).get(param, [""])
                if q[0]:
                    console.print(f"[yellow]search[/yellow] {host}  [bold]{q[0]}[/bold]")
                return
        console.print(f"[green]nav[/green]   {host}  {u[:60]}")

    args = ["--disable-blink-features=AutomationControlled", "--no-first-run",
            "--password-store=basic", "--use-mock-keychain"]
    if profile.webrtc_mode in ("proxy_only", "disabled"):
        args.append("--force-webrtc-ip-handling-policy=disable_non_proxied_udp")
    args += doh.chromium_args()

    console.print(Panel.fit(
        f"[bold cyan]IceBerg[/bold cyan]  profile: [yellow]{profile.name}[/yellow]\n"
        f"UA: {profile.user_agent[:60]}...   DoH: {profile.doh_provider}   "
        f"proxy: {profile.proxy or 'none'}", title="session " + session, border_style="cyan"))

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=headless, args=args)
        ctx = browser.new_context(
            user_agent=profile.user_agent, locale=profile.locale,
            timezone_id=profile.timezone,
            viewport={"width": profile.screen_width, "height": profile.screen_height},
            device_scale_factor=profile.device_pixel_ratio,
            proxy=_proxy_dict(profile.proxy) if profile.proxy else None,
            extra_http_headers=_headers(profile))
        ctx.add_init_script(f"window.__VEIL__={json.dumps(_spoof_config(profile))};")
        ctx.add_init_script(SPOOF_JS.read_text())
        page = ctx.new_page()
        page.on("framenavigated", on_nav)
        target = "file://" + str(SELFTEST) if selftest else (url or "about:blank")
        page.goto(target)
        console.print("[green]Live.[/green] Type/search - every DNS/nav/query shows above.")
        console.print("[dim]Close the window to end.[/dim]\n")
        try:
            browser.wait_for_event("disconnected", timeout=0)
        except KeyboardInterrupt:
            pass
        finally:
            try:
                ctx.close(); browser.close()
            except Exception:
                pass
