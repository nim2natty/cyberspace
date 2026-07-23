"""Ordered Cyberdeck prompt records, labels, migration, and entry-point wiring."""
from __future__ import annotations

import json
import os


def _isolate(monkeypatch, tmp_path):
    import cyberspace.config as config
    import cyberspace.cyberdeck.prompts as prompts
    monkeypatch.setattr(config, "HOME", tmp_path)
    monkeypatch.setattr(config, "ensure_dirs", lambda: tmp_path.mkdir(parents=True, exist_ok=True))
    monkeypatch.setattr(prompts, "HOME", tmp_path)
    monkeypatch.setattr(prompts, "ensure_dirs", lambda: tmp_path.mkdir(parents=True, exist_ok=True))
    monkeypatch.setattr(prompts, "CYBERDECK_DIR", tmp_path / "cyberdeck")
    monkeypatch.setattr(prompts, "PROMPTS_FILE", tmp_path / "cyberdeck" / "prompts.jsonl")
    monkeypatch.setattr(prompts, "LOCK_FILE", tmp_path / "cyberdeck" / ".prompts.lock")
    monkeypatch.setattr(prompts, "MIGRATION_FILE", tmp_path / "cyberdeck" / ".prompts-migrated")
    return prompts


def test_prompts_are_ordered_and_automatically_labeled(monkeypatch, tmp_path):
    prompts = _isolate(monkeypatch, tmp_path)
    first = prompts.record_prompt("Scan my authorized home router for open ports")
    second = prompts.record_prompt("Summarize the service-version findings")
    prompts.complete_prompt(second["sequence"], "summary")

    rows = prompts.list_prompts(limit=10)
    assert [row["sequence"] for row in rows] == [1, 2]
    assert rows[0]["label"] == "scan-authorized-home-router-open-ports"
    assert rows[0]["label_source"] == "automatic"
    assert rows[1]["response"] == "summary" and rows[1]["status"] == "completed"


def test_explicit_label_is_preserved_and_can_be_changed(monkeypatch, tmp_path):
    prompts = _isolate(monkeypatch, tmp_path)
    row = prompts.record_prompt("[label: Home Lab] inspect DHCP leases")
    assert row["label"] == "home-lab" and row["label_source"] == "user"
    assert prompts.set_label(row["sequence"], "Router Review")
    saved = prompts.get_prompt(row["sequence"])
    assert saved["label"] == "router-review"
    assert prompts.list_prompts(label="Router Review")[0]["sequence"] == row["sequence"]


def test_pending_prompt_survives_provider_failure(monkeypatch, tmp_path):
    prompts = _isolate(monkeypatch, tmp_path)
    from cyberspace.agent import core
    from cyberspace.agent.llm import LLMConfig, ProviderError
    from cyberspace.modules.base import ToolRegistry

    monkeypatch.setattr(core, "get_provider", lambda cfg: object())
    monkeypatch.setattr(core, "build_system_prompt", lambda base="": "system")
    monkeypatch.setattr(core, "chat_with_failover",
                        lambda *args, **kwargs: (_ for _ in ()).throw(ProviderError("offline")))
    agent = core.Agent(LLMConfig(), registry=ToolRegistry(), include_project_tools=False)
    try:
        agent.ask("check the test host")
    except ProviderError:
        pass
    rows = prompts.list_prompts()
    assert len(rows) == 1
    assert rows[0]["prompt"] == "check the test host"
    assert rows[0]["status"] == "failed"
    assert "offline" in rows[0]["response"]


def test_agent_and_swarm_attach_responses(monkeypatch, tmp_path):
    prompts = _isolate(monkeypatch, tmp_path)
    from cyberspace.agent import core
    from cyberspace.agent.llm import AgentResponse, LLMConfig
    from cyberspace.modules.base import ToolRegistry
    import cyberspace.swarm as swarm

    monkeypatch.setattr(core, "get_provider", lambda cfg: object())
    monkeypatch.setattr(core, "build_system_prompt", lambda base="": "system")
    monkeypatch.setattr(core, "chat_with_failover",
                        lambda *args, **kwargs: AgentResponse(text="agent response"))
    agent = core.Agent(LLMConfig(), registry=ToolRegistry(), include_project_tools=False)
    assert agent.ask("agent prompt") == "agent response"

    monkeypatch.setattr(swarm, "get_provider", lambda cfg: object())
    monkeypatch.setattr(swarm, "build_system_prompt", lambda base="": "system")
    monkeypatch.setattr(swarm, "chat_with_failover",
                        lambda *args, **kwargs: AgentResponse(text="swarm response"))
    worker = swarm.Swarm(LLMConfig(), ghost_mode=True)
    assert worker.ask("write up the findings").startswith("STAGE UNCERTAIN")

    rows = prompts.list_prompts()
    assert [row["source"] for row in rows] == ["agent", "swarm-ghost"]
    assert rows[0]["response"] == "agent response"
    assert rows[1]["response"].startswith("STAGE UNCERTAIN")


def test_existing_project_and_swarm_prompts_migrate_once_in_timestamp_order(monkeypatch, tmp_path):
    prompts = _isolate(monkeypatch, tmp_path)
    project_dir = tmp_path / "projects" / "lab"
    project_dir.mkdir(parents=True)
    (project_dir / "prompts.jsonl").write_text(json.dumps({
        "ts": "2026-01-02T00:00:00", "prompt": "second prompt",
        "response": "done", "source": "agent",
    }) + "\n")
    memory_dir = tmp_path / "memory"
    memory_dir.mkdir()
    (memory_dir / "episodes.jsonl").write_text(json.dumps({
        "ts": "2026-01-01T00:00:00", "action": "user_objective",
        "args": {"prompt": "first prompt"},
    }) + "\n")

    first_read = prompts.list_prompts()
    second_read = prompts.list_prompts()
    assert [row["prompt"] for row in first_read] == ["first prompt", "second prompt"]
    assert [row["sequence"] for row in first_read] == [1, 2]
    assert second_read == first_read


def test_project_and_swarm_copies_with_nearby_timestamps_migrate_once(monkeypatch, tmp_path):
    prompts = _isolate(monkeypatch, tmp_path)
    project_dir = tmp_path / "projects" / "lab"
    project_dir.mkdir(parents=True)
    (project_dir / "prompts.jsonl").write_text(json.dumps({
        "ts": "2026-01-01T00:00:05", "prompt": "same prompt",
        "response": "project response", "source": "agent",
    }) + "\n")
    memory_dir = tmp_path / "memory"
    memory_dir.mkdir()
    (memory_dir / "episodes.jsonl").write_text(json.dumps({
        "ts": "2026-01-01T00:00:00", "action": "user_objective",
        "args": {"prompt": "same prompt"},
    }) + "\n")
    rows = prompts.list_prompts()
    assert len(rows) == 1
    assert rows[0]["response"] == "project response"


def test_prompt_store_uses_private_posix_permissions(monkeypatch, tmp_path):
    prompts = _isolate(monkeypatch, tmp_path)
    prompts.record_prompt("permission test prompt")
    if os.name != "nt":
        assert (tmp_path / "cyberdeck").stat().st_mode & 0o777 == 0o700
        assert prompts.PROMPTS_FILE.stat().st_mode & 0o777 == 0o600


def test_llm_prompt_tool_is_scoped_to_active_project(monkeypatch, tmp_path):
    prompts = _isolate(monkeypatch, tmp_path)
    import cyberspace.projects as projects
    import cyberspace.cyberdeck.module as module
    monkeypatch.setattr(projects, "PROJECTS_DIR", tmp_path / "projects")
    monkeypatch.setattr(projects, "ACTIVE_FILE", tmp_path / "active_project")
    projects.create("alpha")
    prompts.record_prompt("alpha secret prompt", project="alpha")
    prompts.record_prompt("beta separate prompt", project="beta")
    result = module._tool_prompts(limit=20)
    assert "alpha secret prompt" in result
    assert "beta separate prompt" not in result


def test_direct_list_can_access_all_projects(monkeypatch, tmp_path):
    prompts = _isolate(monkeypatch, tmp_path)
    prompts.record_prompt("alpha prompt", project="alpha")
    prompts.record_prompt("beta prompt", project="beta")
    assert [row["project"] for row in prompts.list_prompts()] == ["alpha", "beta"]


def test_relabel_as_first_command_triggers_migration(monkeypatch, tmp_path):
    prompts = _isolate(monkeypatch, tmp_path)
    project_dir = tmp_path / "projects" / "lab"
    project_dir.mkdir(parents=True)
    (project_dir / "prompts.jsonl").write_text(json.dumps({
        "ts": "2026-01-01T00:00:00", "prompt": "migrated prompt",
        "response": "done", "source": "agent",
    }) + "\n")
    assert prompts.set_label(1, "Imported Lab")
    assert prompts.get_prompt(1)["label"] == "imported-lab"


def test_cyberdeck_cli_exposes_prompt_commands():
    from cyberspace.cyberdeck.module import MODULE
    app = MODULE.build_cli()
    names = {command.name for command in app.registered_commands}
    assert {"prompts", "prompt", "label"} <= names
