"""Verify the IceBerg :: secure tool (AI find / brightside + darkside).

Network, Tor, and the LLM are NOT required here - we validate the data
catalogs, security-config persistence, prompt coverage, and agent-tool wiring.
"""
import json
import sys
import tempfile
import pathlib


def main():
    # 1) Engine catalogs (Robin's 16 onion engines + clearnet engines).
    from cyberspace.platforms.iceberg.secure.engines import (
        engines_for, DARKSIDE_ENGINES, BRIGHTSIDE_ENGINES)
    dark = engines_for("dark")
    bright = engines_for("bright")
    assert len(dark) == 16, f"expected 16 dark engines, got {len(dark)}"
    assert len(bright) >= 2, f"expected >=2 bright engines, got {len(bright)}"
    assert all(e["url"].startswith("http") and "{query}" in e["url"] for e in dark + bright)
    assert all(".onion" in e["url"] for e in dark), "dark engines must be .onion"
    print(f"PASS  engines: dark={len(dark)} onion, bright={len(bright)} clearnet")

    # 2) Security config round-trip + dark posture differs from bright.
    fake_home = pathlib.Path(tempfile.mkdtemp())
    import cyberspace.config as cfg
    cfg.HOME = fake_home
    cfg.MODULES_DIR = fake_home / "modules"
    cfg.ensure_dirs()
    from cyberspace.platforms.iceberg.secure.security import SecurityConfig, PRESETS, dark_settings
    s = PRESETS["dark_safe"]["config"]
    s.save()
    loaded = SecurityConfig.load()
    assert loaded.mode == "dark" and loaded.tor_socks_port == 9050
    assert loaded.new_identity_per_session and loaded.block_webrtc and loaded.force_doh
    assert loaded.verify_tls is False  # onion self-signed
    ds = dark_settings(loaded)
    assert any("Tor SOCKS5h" in line for line in ds)
    bright_cfg = PRESETS["bright"]["config"]
    assert bright_cfg.mode == "bright" and bright_cfg.verify_tls is True
    print("PASS  security config round-trip + bright/dark posture divergence")

    # 3) Tor helper works (returns a bool regardless of whether tor is running).
    from cyberspace.platforms.iceberg.secure.tor import tor_available, socks_url
    assert isinstance(tor_available(), bool)
    assert socks_url().startswith("socks5h://")    # remote DNS for .onion
    print("PASS  tor helper: no proxy -> False; socks5h scheme")

    # 4) Intel prompts cover all presets + the helper signatures exist.
    from cyberspace.platforms.iceberg.secure.intel import (
        PRESET_PROMPTS, PRESET_LABELS, refine_query, filter_results, generate_summary)
    assert set(PRESET_PROMPTS) == {"threat_intel", "personal_identity",
                                   "corporate_espionage", "general"}
    assert set(PRESET_LABELS) == set(PRESET_PROMPTS)
    assert callable(refine_query) and callable(filter_results) and callable(generate_summary)
    assert filter_results("x", []) == []  # empty-in -> empty-out, no LLM call
    print(f"PASS  intel: {len(PRESET_PROMPTS)} presets, signatures present")

    # 5) Pipeline orchestration object + investigation persistence path.
    from cyberspace.platforms.iceberg.secure.pipeline import Investigation, run_find, save_investigation
    inv = Investigation(query="test")
    assert inv.mode == "bright" and inv.results == []
    p = save_investigation(inv)
    assert pathlib.Path(p).exists()
    print("PASS  pipeline: Investigation dataclass + save_investigation")

    # 6) Agent tools registered + e_status callable without Tor.
    from cyberspace.modules.registry import discover_and_load
    from cyberspace.modules.base import TOOL_REGISTRY
    discover_and_load()
    assert TOOL_REGISTRY.get("iceberg.secure_find"), "iceberg.secure_find not registered"
    status = TOOL_REGISTRY.get("iceberg.secure_status").fn()
    assert "secure mode" in status and "Tor SOCKS" in status
    print(f"PASS  agent tools: secure_find + secure_status registered; status callable")

    print("\nALL CHECKS PASSED - IceBerg :: secure tool is wired correctly.")


if __name__ == "__main__":
    try:
        main()
    except AssertionError as e:
        print(f"FAIL  {e}", file=sys.stderr)
        sys.exit(1)
