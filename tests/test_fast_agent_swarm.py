"""Bounded one-plan Agent and Swarm command execution regressions."""
from __future__ import annotations

import io
import time

from rich.console import Console


def _disable_prompt_io(monkeypatch):
    import cyberspace.cyberdeck.prompts as prompts
    monkeypatch.setattr(prompts, "record_prompt", lambda *a, **k: {"sequence": 1})
    monkeypatch.setattr(prompts, "complete_prompt", lambda *a, **k: None)


def _fast_tools():
    from cyberspace.modules.base import Tool

    def run(target):
        time.sleep(0.12)
        return f'{{"status": "pass", "evidence": "Host is up {target}"}}'

    schema = {"type": "object", "properties": {
        "target": {"type": "string"}}, "required": ["target"]}
    return [
        Tool("airbender.fast_one", "first independent host probe", schema, run),
        Tool("airbender.fast_two", "second independent host probe", schema, run),
    ]


def test_agent_plans_once_executes_command_list_concurrently(monkeypatch):
    from cyberspace.agent import core
    from cyberspace.agent.llm import AgentResponse, LLMConfig, ToolCall
    from cyberspace.modules.base import ToolRegistry

    _disable_prompt_io(monkeypatch)
    tools = _fast_tools()
    registry = ToolRegistry()
    for tool in tools:
        registry.register(tool)
    calls = []

    def fake_chat(provider, messages, available, console):
        calls.append((messages, available))
        assert "complete bounded operation in ONE response" in messages[0]["content"]
        return AgentResponse(tool_calls=[
            ToolCall(tools[0].name, {"target": "10.0.0.2"}, "one"),
            ToolCall(tools[1].name, {"target": "10.0.0.3"}, "two"),
        ])

    monkeypatch.setattr(core, "get_provider", lambda cfg: object())
    monkeypatch.setattr(core, "chat_with_failover", fake_chat)
    stream = io.StringIO()
    agent = core.Agent(LLMConfig(), registry=registry, include_project_tools=False,
                       console=Console(file=stream, force_terminal=False))
    monkeypatch.setattr(agent, "_save_to_project", lambda *a: None)
    started = time.perf_counter()
    result = agent.ask("probe 10.0.0.2 and 10.0.0.3 in my authorized lab")
    elapsed = time.perf_counter() - started

    assert len(calls) == 1
    assert elapsed < 0.22
    assert result.startswith("# Command execution — PASS")
    assert '"target": "10.0.0.2"' in result
    assert "Success criteria:" in result and "Verification:" in result
    assert "concurrently in" in result
    assert "Evidence:" in result and "Host is up" in result
    visible = stream.getvalue()
    assert "Command plan (2)" in visible
    assert "1." in visible and "2." in visible


def test_swarm_routes_without_outer_model_and_executes_once(monkeypatch):
    import cyberspace.swarm as swarm
    from cyberspace.agent.llm import AgentResponse, LLMConfig, ToolCall

    _disable_prompt_io(monkeypatch)
    tools = _fast_tools()
    calls = []

    def fake_chat(provider, messages, available, console):
        calls.append((messages, available))
        assert available == tools
        assert "Return the complete precise command list" in messages[-1]["content"]
        return AgentResponse(tool_calls=[
            ToolCall(tools[0].name, {"target": "10.0.0.2"}, "one"),
            ToolCall(tools[1].name, {"target": "10.0.0.3"}, "two"),
        ])

    monkeypatch.setattr(swarm, "get_provider", lambda cfg: object())
    monkeypatch.setattr(swarm, "chat_with_failover", fake_chat)
    monkeypatch.setattr(swarm, "_scoped_tools", lambda prefixes: tools)
    stream = io.StringIO()
    worker = swarm.Swarm(LLMConfig(), console=Console(
        file=stream, force_terminal=False), ghost_mode=True)
    monkeypatch.setattr(worker, "_save_to_project", lambda *a: None)
    monkeypatch.setattr(worker, "_record_objective", lambda *a: None)
    started = time.perf_counter()
    result = worker.ask("scan 10.0.0.2 and 10.0.0.3 in my authorized lab")
    elapsed = time.perf_counter() - started

    assert len(calls) == 1
    assert elapsed < 0.22
    assert result.startswith("# Command execution — PASS")
    assert "Aggregate stage criterion: recon" in result
    assert "PASS `recon.surface_mapped`" in result
    assert "Command plan (2)" in stream.getvalue()


def test_imprecise_batch_fails_before_any_command_runs():
    from cyberspace.agent.llm import ToolCall
    from cyberspace.modules.base import Tool
    from cyberspace.tooling import execute_tool_batch

    ran = []
    tool = Tool("shadowdragon.exact", "exact test", {"type": "object", "properties": {
        "url": {"type": "string"}}, "required": ["url"]}, lambda url: ran.append(url))
    report, executions = execute_tool_batch([
        ToolCall(tool.name, {}, "bad")], [tool], "test the application")
    assert report.startswith("# Command plan — FAIL")
    assert "requires 'url'" in report
    assert executions == [] and ran == []


def test_oversized_batch_is_not_silently_truncated():
    from cyberspace.agent.llm import ToolCall
    from cyberspace.modules.base import Tool
    from cyberspace.tooling import execute_tool_batch

    ran = []
    tool = Tool("airbender.probe", "probe", {"type": "object", "properties": {}},
                lambda: ran.append(True))
    report, executions = execute_tool_batch(
        [ToolCall(tool.name, {}, str(index)) for index in range(7)], [tool], "probe")
    assert "proposed 7 commands" in report and "maximum is 6" in report
    assert executions == [] and ran == []