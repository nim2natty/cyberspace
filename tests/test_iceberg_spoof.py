"""Verify IceBerg's anti-fingerprinting works inside cyberspace.

Launches headless Chromium WITH and WITHOUT IceBerg spoofing, reads back the
fingerprint vectors, and confirms the spoofed identity differs from the host.
"""
import sys


def probe():
    from playwright.sync_api import sync_playwright
    JS = """
    () => ({
      userAgent: navigator.userAgent,
      platform: navigator.platform,
      hardwareConcurrency: navigator.hardwareConcurrency,
      deviceMemory: navigator.deviceMemory,
      webdriver: navigator.webdriver,
      screen: screen.width + 'x' + screen.height,
      intlTz: Intl.DateTimeFormat().resolvedOptions().timeZone,
      tzOffset: new Date().getTimezoneOffset(),
      webglVendor: (function(){try{var c=document.createElement('canvas');var g=c.getContext('webgl');var d=g.getExtension('WEBGL_debug_renderer_info');return g.getParameter(d.UNMASKED_VENDOR_WEBGL);}catch(e){return 'err';}})(),
      canvasHash: (function(){var c=document.createElement('canvas');c.width=200;c.height=30;var x=c.getContext('2d');x.textBaseline='top';x.font='14px Arial';x.fillStyle='#069';x.fillText('cyberspace-probe',2,2);var d=c.toDataURL();var h=0;for(var i=0;i<d.length;i++){h=(h*31+d.charCodeAt(i))|0;}return h;})()
    })
    """
    with sync_playwright() as pw:
        # raw host
        b = pw.chromium.launch(headless=True)
        ctx = b.new_context()
        p = ctx.new_page(); p.goto("about:blank")
        real = p.evaluate(JS)
        ctx.close(); b.close()

        # IceBerg spoofed
        from cyberspace.platforms.iceberg.profiles import FingerprintProfile
        from cyberspace.platforms.iceberg.browser import _spoof_config, _headers, SPOOF_JS, DoH
        import json
        prof = FingerprintProfile.from_persona("verify", "win-chrome")
        doh = DoH(prof.doh_provider)
        args = ["--disable-blink-features=AutomationControlled", "--no-first-run",
                "--password-store=basic", "--use-mock-keychain",
                "--force-webrtc-ip-handling-policy=disable_non_proxied_udp"]
        args += doh.chromium_args()
        b = pw.chromium.launch(headless=True, args=args)
        ctx = b.new_context(
            user_agent=prof.user_agent, locale=prof.locale, timezone_id=prof.timezone,
            viewport={"width": prof.screen_width, "height": prof.screen_height},
            device_scale_factor=prof.device_pixel_ratio, extra_http_headers=_headers(prof))
        ctx.add_init_script(f"window.__VEIL__={json.dumps(_spoof_config(prof))};")
        ctx.add_init_script(SPOOF_JS.read_text())
        p = ctx.new_page(); p.goto("about:blank")
        spoof = p.evaluate(JS)
        ctx.close(); b.close()
    return real, spoof, prof


def main():
    real, spoof, prof = probe()
    checks = {
        "userAgent Windows": "Windows" in spoof["userAgent"],
        "platform Win32": spoof["platform"] == "Win32",
        "cores match profile": spoof["hardwareConcurrency"] == prof.hardware_concurrency,
        "deviceMemory set": spoof["deviceMemory"] == prof.device_memory,
        "webdriver hidden": spoof["webdriver"] is False,
        "timezone spoofed": spoof["intlTz"] == prof.timezone and spoof["tzOffset"] != real["tzOffset"],
        "WebGL NVIDIA": "NVIDIA" in spoof["webglVendor"],
        "canvas noise differs": spoof["canvasHash"] != real["canvasHash"],
    }
    print(f"{'vector':<26}{'real':<22}{'spoofed':<22}ok?")
    print("-" * 80)
    for k, ok in checks.items():
        field = k.split()[0].lower()
        rv = str(real.get(field, real.get("userAgent","") if "user" in k else ""))
        sv = str(spoof.get(field, ""))
        print(f"{k:<26}{rv[:20]:<22}{sv[:20]:<22}{'OK' if ok else 'XX'}")
    print("-" * 80)
    all_ok = all(checks.values())
    print("RESULT:", "ICEBERG SPOOFING VERIFIED" if all_ok else "SOME VECTORS FAILED")
    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()
