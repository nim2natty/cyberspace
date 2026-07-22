"""Platform-wide success-contract and RoboDaddy prompt-guide regressions."""
from __future__ import annotations


def test_every_registered_tool_has_contract_in_provider_schema():
    from cyberspace.modules.base import TOOL_REGISTRY
    from cyberspace.modules.registry import discover_and_load

    discover_and_load()
    assert TOOL_REGISTRY.all()
    for tool in TOOL_REGISTRY.all():
        assert tool.success_criteria, tool.name
        assert tool.verification, tool.name
        schema = tool.to_openai()["function"]
        assert "Success contract" in schema["description"], tool.name
        assert "Verification:" in schema["description"], tool.name


def test_anthropic_provider_uses_same_success_aware_description(monkeypatch):
    from cyberspace.agent.llm import AnthropicProvider, LLMConfig
    from cyberspace.modules.base import Tool

    captured = {}
    provider = AnthropicProvider(LLMConfig(provider="anthropic", api_key="test", model="test"))
    monkeypatch.setattr(provider, "_post", lambda url, payload, headers:
                        captured.setdefault("payload", payload) or {"content": []})
    tool = Tool("example.lookup", "Look up a signed record.", {}, lambda: "record")
    provider.chat([{"role": "user", "content": "look it up"}], [tool])
    native = captured["payload"]["tools"][0]
    description = native["description"]
    assert "Success contract" in description and "Verification:" in description
    assert "." not in native["name"] and len(native["name"]) <= 64
    assert native["input_schema"] == {"type": "object", "properties": {}}


def test_external_tool_gets_nonempty_fallback_contract():
    from cyberspace.modules.base import Tool, ToolRegistry

    registry = ToolRegistry()
    registry.register(Tool("example.lookup", "Look up a signed record.", {}, lambda: "record"))
    tool = registry.get("example.lookup")
    assert tool.success_criteria
    assert "signed record" in tool.success_criteria[0]
    assert tool.verification


def test_runtime_check_never_calls_arbitrary_text_a_pass():
    from cyberspace.success import assess_tool_output

    assert assess_tool_output("success_criteria required before training")[0] == "fail"
    assert assess_tool_output("some non-empty output")[0] == "uncertain"
    assert assess_tool_output('{"status": "pass", "evidence": "checked"}')[0] == "pass"
    assert assess_tool_output(
        '{"status": "pass", "evidence": "all required fields present"}')[0] == "pass"


def test_system_prompt_always_contains_success_protocol(monkeypatch):
    from cyberspace.agent.core import build_system_prompt

    prompt = build_system_prompt("base instructions")
    assert "Mandatory success protocol" in prompt
    assert all(status in prompt for status in ("pass", "fail", "uncertain", "not-tested"))


def test_swarm_delegate_requires_and_forwards_criteria(monkeypatch):
    import cyberspace.swarm as swarm
    from cyberspace.agent.llm import AgentResponse, LLMConfig

    seen = {}
    monkeypatch.setattr(swarm, "get_provider", lambda cfg: object())

    def fake_chat(provider, messages, tools, console):
        seen["prompt"] = messages[-1]["content"]
        return AgentResponse(text="Criterion: pass; evidence: host 10.0.0.2")

    monkeypatch.setattr(swarm, "chat_with_failover", fake_chat)
    worker = swarm.Swarm(LLMConfig())
    schema = worker._delegate_tool().parameters
    assert "success_criteria" in schema["required"]
    result = worker.delegate("recon", "find hosts", "At least one host is evidenced")
    assert "<success_criteria>At least one host is evidenced</success_criteria>" in seen["prompt"]
    assert "pass" in result


def test_swarm_downgrades_unverified_specialist_prose(monkeypatch):
    import cyberspace.swarm as swarm
    from cyberspace.agent.llm import AgentResponse, LLMConfig
    monkeypatch.setattr(swarm, "get_provider", lambda cfg: object())
    monkeypatch.setattr(swarm, "chat_with_failover",
                        lambda *args, **kwargs: AgentResponse(text="Looks good to me."))
    worker = swarm.Swarm(LLMConfig())
    result = worker.delegate("recon", "find hosts", "At least one host is evidenced")
    assert result.startswith("STAGE UNCERTAIN")


def test_robodaddy_criteria_persist_into_plan_prompt_and_eval(tmp_path, monkeypatch):
    import cyberspace.config as config
    from cyberspace.platforms.robodaddy import registry, train
    from cyberspace.platforms.robodaddy.parameters import profile
    from cyberspace.platforms.robodaddy.plan import build_plan

    root = tmp_path / "robodaddy"
    monkeypatch.setattr(config, "MODULES_DIR", tmp_path)
    monkeypatch.setattr(registry, "T_DIR", root)
    monkeypatch.setattr(registry, "MODELS_FILE", root / "models.json")
    monkeypatch.setattr(registry, "KEYS_FILE", root / "keys.json")
    monkeypatch.setattr(registry, "LOCK_FILE", root / ".registry.lock")
    monkeypatch.setattr(train, "JOBS_DIR", root / "jobs")

    params = profile("custom_blank")
    params.success_criteria = ["At least 90% exact match on 100 held-out cases"]
    plan = build_plan("general", parameters=params)
    train.write_job_files(plan)
    assert plan.success_criteria == params.success_criteria
    assert "<success_criteria>" in plan.system_prompt
    import json
    saved = json.loads((root / "jobs" / plan.name / "plan.json").read_text())
    evaluation = json.loads((root / "jobs" / plan.name / "evaluation.json").read_text())
    assert saved["success_criteria"] == params.success_criteria
    assert evaluation["status"] == "not-tested"
    assert evaluation["criteria"][0]["status"] == "not-tested"


def test_robodaddy_lower_level_apis_reject_missing_criteria():
    import pytest
    from cyberspace.platforms.robodaddy.parameters import profile
    from cyberspace.platforms.robodaddy.plan import TrainingPlan, build_plan
    from cyberspace.platforms.robodaddy.train import run_training

    with pytest.raises(ValueError, match="success criteria"):
        build_plan("general")
    params = profile("custom_blank")
    with pytest.raises(ValueError, match="success criteria"):
        build_plan("general", parameters=params)
    empty = TrainingPlan("empty", "general", "qwen2.5-7b", "tatsu-lab/alpaca")
    with pytest.raises(ValueError, match="success criteria"):
        run_training(empty)
    from cyberspace.platforms.robodaddy.jobs import launch_background
    with pytest.raises(ValueError, match="success criteria"):
        launch_background(empty)


def test_robodaddy_rejects_vague_nonempty_criteria():
    import pytest
    from cyberspace.platforms.robodaddy.parameters import profile
    from cyberspace.platforms.robodaddy.plan import build_plan
    from cyberspace.platforms.robodaddy.prompt_guide import validate_success_criteria
    for vague in ("x", "works", "be accurate"):
        with pytest.raises(ValueError, match="measurable"):
            validate_success_criteria(vague)
    params = profile("custom_blank")
    params.success_criteria = ["works"]
    with pytest.raises(ValueError, match="measurable"):
        build_plan("general", parameters=params)


def test_success_criteria_parameter_coercion_keeps_a_list():
    from cyberspace.platforms.robodaddy.cli import _coerce_value
    from cyberspace.platforms.robodaddy.module import _coerce_for_agent
    from cyberspace.platforms.robodaddy.parameters import merge_overrides, profile

    params = profile("custom_blank")
    cli_value = _coerce_value(params, "success_criteria", "90% pass; unsupported claims = 0")
    agent_value = _coerce_for_agent(params, "success_criteria", "90% pass; citations valid")
    assert cli_value == ["90% pass", "unsupported claims = 0"]
    assert agent_value == ["90% pass", "citations valid"]
    updated = merge_overrides(
        params, success_criteria="At least 90% pass on 100 tests; unsupported claims = 0")
    assert updated.success_criteria == [
        "At least 90% pass on 100 tests", "unsupported claims = 0"]


def test_serving_preserves_independent_evaluation_status(tmp_path, monkeypatch):
    import cyberspace.config as config
    import cyberspace.credentials as credentials
    from cyberspace.platforms.robodaddy import registry
    root = tmp_path / "robodaddy"
    monkeypatch.setattr(config, "MODULES_DIR", tmp_path)
    monkeypatch.setattr(registry, "T_DIR", root)
    monkeypatch.setattr(registry, "MODELS_FILE", root / "models.json")
    monkeypatch.setattr(registry, "KEYS_FILE", root / "keys.json")
    monkeypatch.setattr(registry, "LOCK_FILE", root / ".registry.lock")
    monkeypatch.setattr(credentials, "set_secret", lambda *args: None)
    model = registry.TrainedModel(
        "model", "qwen2.5-7b", "data/set", "general", "qlora",
        status="trained-not-evaluated", evaluation_status="not-tested")
    registry.upsert_model(model)
    registry.issue_key("model", "http://localhost/v1")
    served = registry.get_model("model")
    assert served.status == "served"
    assert served.evaluation_status == "not-tested"


def test_prompt_guide_teaches_grounding_and_anthropic_eval_order():
    from cyberspace.platforms.robodaddy.prompt_guide import ANTHROPIC_PROMPT_GUIDE

    guide = ANTHROPIC_PROMPT_GUIDE.lower()
    for required in ("define success", "exact/string match", "xml", "i don't know",
                     "never invent a citation", "edge cases", "official sources"):
        assert required in guide