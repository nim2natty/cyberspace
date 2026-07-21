from __future__ import annotations

import json


def test_agent_config_never_writes_api_key(tmp_path, monkeypatch):
    import cyberspace.agent.config as config
    from cyberspace.agent.llm import LLMConfig

    saved = {}
    monkeypatch.setattr(config, "AGENT_FILE", tmp_path / "agent.json")
    monkeypatch.setattr(config, "ensure_dirs", lambda: None)
    monkeypatch.setattr(config, "set_secret", lambda name, value: saved.update({name: value}))
    monkeypatch.setattr(config, "get_secret", lambda name, env_var="": saved.get(name, ""))

    storage = config.save_config(LLMConfig(provider="openai", model="test", api_key="secret-key"))
    raw = (tmp_path / "agent.json").read_text()
    assert "secret-key" not in raw
    assert json.loads(raw)["api_key"] == ""
    assert storage == "native credential store"
    assert config.load_config().api_key == "secret-key"