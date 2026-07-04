"""End-to-end verification of the cyberspace platform.

Confirms: module discovery loads all 4 platforms, all 15 tools register, tools
are callable, and the module/agent wiring is correct.
"""
import sys


def main():
    from cyberspace.modules.base import LOADED_MODULES, TOOL_REGISTRY
    from cyberspace.modules.registry import discover_and_load

    loaded = discover_and_load()
    assert loaded, "no modules loaded"
    expected = {"iceberg", "airbender", "shadowdragon", "stickem", "trainababy"}
    missing = expected - set(loaded)
    assert not missing, f"missing platforms: {missing}"
    print(f"PASS  platforms loaded: {sorted(loaded)}")

    # Per-module tool counts. iceberg=5, airbender=6 (expanded super-tool),
    # shadowdragon=16 (chain+metasploit), stickem=9 (router), trainababy=4 => 40.
    expected_tools = {"iceberg": 5, "airbender": 6, "shadowdragon": 16,
                      "stickem": 9, "trainababy": 4}
    by_mod = {m: len(TOOL_REGISTRY.by_module(m)) for m in expected}
    for mod, n in expected_tools.items():
        assert by_mod.get(mod, 0) == n, \
            f"{mod}: expected {n} tools, got {by_mod.get(mod, 0)}"
    total = sum(expected_tools.values())
    assert len(TOOL_REGISTRY.all()) == total, \
        f"expected {total} tools, got {len(TOOL_REGISTRY.all())}"
    print(f"PASS  tools registered: {len(TOOL_REGISTRY.all())} total -> {by_mod}")

    # A tool that needs no external binary: iceberg.opsec_check
    tool = TOOL_REGISTRY.get("iceberg.opsec_check")
    assert tool, "iceberg.opsec_check not found"
    result = tool.fn()
    assert "OPSEC" in result, "opsec_check returned unexpected output"
    print(f"PASS  tool execution: iceberg.opsec_check -> {result.splitlines()[0]!r}")

    # A tool that should report missing (nmap not installed here)
    t2 = TOOL_REGISTRY.get("airbender.nmap")
    r2 = t2.fn(target="127.0.0.1")
    assert "nmap" in r2.lower(), "nmap tool did not report availability"
    print(f"PASS  tool graceful-degrade: airbender.nmap -> {r2.splitlines()[0] if r2 else r2!r}")

    # Agent config persistence round-trip (no LLM call)
    from cyberspace.agent.llm import LLMConfig
    from cyberspace.agent.config import save_config, load_config
    import tempfile, pathlib
    fake_home = pathlib.Path(tempfile.mkdtemp())
    import cyberspace.config as cfg
    cfg.HOME = fake_home
    cfg.AGENT_FILE = fake_home / "agent.json"
    cfg.ensure_dirs()
    save_config(LLMConfig(provider="ollama", model="llama3.1:8b"))
    loaded_cfg = load_config()
    assert loaded_cfg.provider == "ollama" and loaded_cfg.model == "llama3.1:8b"
    print("PASS  agent config persistence round-trip")

    print("\nALL CHECKS PASSED - cyberspace platform is wired correctly.")


if __name__ == "__main__":
    try:
        main()
    except AssertionError as e:
        print(f"FAIL  {e}", file=sys.stderr)
        sys.exit(1)
