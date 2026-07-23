"""Cross-platform tool compilation, elevation, and updater regressions."""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace


def _value(name, spec):
    if spec.get("enum"):
        return spec["enum"][0]
    kind = spec.get("type", "string")
    if kind == "integer":
        return 2
    if kind == "number":
        return 0.2
    if kind == "boolean":
        return True
    if kind == "array":
        return ["At least 90% pass across 100 held-out tests"]
    samples = {
        "target": "10.10.20.0/24", "url": "https://lab.example/",
        "domain": "lab.example", "hashfile": "/tmp/hashes.txt",
        "hash": "d41d8cd98f00b204e9800998ecf8427e", "ssid": "lab-wifi",
        "success_criteria": "At least 90% pass across 100 held-out tests",
        "model_name": "lab-model", "profile": "lab-profile",
        "module": "exploit/test", "lhost": "10.10.20.2",
    }
    return samples.get(name, f"test-{name}")


def test_every_registered_tool_schema_compiles_precisely():
    from cyberspace.modules.base import TOOL_REGISTRY
    from cyberspace.modules.registry import discover_and_load
    from cyberspace.tooling import compile_tool_call

    discover_and_load()
    assert len(TOOL_REGISTRY.all()) >= 58
    for tool in TOOL_REGISTRY.all():
        properties = tool.parameters.get("properties", {})
        supplied = {name: _value(name, properties[name])
                    for name in tool.parameters.get("required", [])}
        compiled = compile_tool_call(tool, supplied, "authorized lab operation")
        assert compiled.tool == tool.name
        assert compiled.platform == tool.module
        assert compiled.stage in {
            "recon", "weapon", "delivery", "exploit", "install", "c2", "objectives"}
        assert set(tool.parameters.get("required", [])) <= set(compiled.arguments)
        assert "category=" in compiled.preview() and "arguments=" in compiled.preview()


def test_compiler_rejects_unknown_ambiguous_and_invalid_arguments():
    import pytest
    from cyberspace.modules.base import Tool
    from cyberspace.tooling import ToolArgumentError, compile_tool_call

    tool = Tool("example.run", "run", {"type": "object", "properties": {
        "profile": {"type": "string"},
        "mode": {"type": "string", "enum": ["safe", "full"]},
    }, "required": ["profile", "mode"]}, lambda **_: None)
    with pytest.raises(ToolArgumentError, match="unsupported"):
        compile_tool_call(tool, {"invented": "x"}, "run it")
    with pytest.raises(ToolArgumentError, match="requires 'profile'"):
        compile_tool_call(tool, {"mode": "safe"}, "run it")
    with pytest.raises(ToolArgumentError, match="must be one of"):
        compile_tool_call(tool, {"profile": "lab", "mode": "danger"}, "run it")


def test_agent_executes_compiled_typed_arguments(monkeypatch):
    from cyberspace.agent import core
    from cyberspace.agent.llm import LLMConfig
    from cyberspace.modules.base import Tool, ToolRegistry

    seen = {}
    registry = ToolRegistry()
    registry.register(Tool("example.run", "run", {"type": "object", "properties": {
        "count": {"type": "integer"}}, "required": ["count"]},
        lambda count: seen.setdefault("count", count)))
    monkeypatch.setattr(core, "get_provider", lambda cfg: object())
    agent = core.Agent(LLMConfig(), registry=registry, include_project_tools=False)
    agent.current_prompt = "run twice"
    result = agent._execute(SimpleNamespace(name="example.run", arguments={"count": "2"}))
    assert seen["count"] == 2
    assert "RUNTIME CHECK" in result


def test_runtime_reports_native_or_container_fact():
    from cyberspace.host import runtime_environment, runtime_summary
    env = runtime_environment()
    assert isinstance(env["container"], bool)
    expected = "container network namespace" if env["container"] else "native host network"
    assert expected in runtime_summary()


def test_elevation_requires_confirmation_and_only_wraps_allowlist(monkeypatch):
    import cyberspace.host as host

    host.disable_elevation()
    monkeypatch.setattr(host, "runtime_environment", lambda: {
        "os": "Linux", "container": False, "admin": False,
        "elevation_enabled": False})
    monkeypatch.setattr(host, "is_available", lambda name: name == "sudo")
    monkeypatch.setattr(host, "which", lambda name: f"/usr/bin/{name}")
    ok, message = host.enable_elevation(confirm=None)
    assert not ok and "confirmation" in message
    ok, _ = host.enable_elevation(confirm=lambda prompt: True, runner=lambda argv: 0)
    assert ok

    commands = []
    monkeypatch.setattr(host.subprocess, "run", lambda command, **kwargs:
                        commands.append(command) or SimpleNamespace(
                            returncode=0, stdout="ok", stderr=""))
    host.run("nmap", ["-sn", "10.0.0.0/24"])
    host.run("whois", ["example.com"])
    assert commands[0][:3] == ["/usr/bin/sudo", "-n", "/usr/bin/nmap"]
    assert commands[1][0] == "/usr/bin/whois"
    host.disable_elevation()


def test_container_elevation_explains_host_network_requirement(monkeypatch):
    import cyberspace.host as host
    monkeypatch.setattr(host, "runtime_environment", lambda: {
        "os": "Linux", "container": True, "admin": True,
        "elevation_enabled": False})
    ok, message = host.enable_elevation(confirm=lambda prompt: True)
    assert not ok
    assert "--network host" in message and "NET_RAW" in message


def test_source_update_refuses_dirty_checkout(tmp_path):
    from cyberspace.updater import update_latest
    (tmp_path / ".git").mkdir()
    (tmp_path / "pyproject.toml").write_text("[project]\n")

    def runner(command, **kwargs):
        return SimpleNamespace(returncode=0, stdout=" M cyberspace/host.py\n", stderr="")

    result = update_latest(root=tmp_path, runner=runner)
    assert not result.ok and "uncommitted changes" in result.message


def test_source_update_fast_forwards_and_refreshes_environment(tmp_path):
    from cyberspace.updater import update_latest
    (tmp_path / ".git").mkdir()
    (tmp_path / "pyproject.toml").write_text("[project]\n")
    python = tmp_path / ".venv" / "bin" / "python"
    python.parent.mkdir(parents=True)
    python.write_text("")
    commands = []

    def runner(command, **kwargs):
        commands.append(command)
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    result = update_latest(root=tmp_path, runner=runner)
    assert result.ok and result.method == "source"
    assert commands[1][-4:] == ["pull", "--ff-only", "origin", "main"]
    assert commands[2] == [str(python), "-m", "pip", "install", "-e", str(tmp_path)]