from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path
from types import SimpleNamespace


def test_live_dataset_discovery_is_bounded_and_normalized():
    from cyberspace.platforms.robodaddy.discovery import discover_datasets

    class Response:
        def raise_for_status(self): pass
        def json(self):
            return [{"id": "owner/useful", "downloads": 42, "likes": 3,
                     "gated": False, "sha": "abc123", "tags": ["license:apache-2.0"]}]

    class Client:
        def get(self, url, params):
            assert params["limit"] <= 25
            return Response()

    found = discover_datasets("useful data", limit=100, client=Client())
    assert found[0]["id"] == "owner/useful"
    assert found[0]["revision"] == "abc123"
    assert found[0]["license"] == "apache-2.0"


def test_scoped_agent_rejects_forged_cross_platform_call(monkeypatch):
    from cyberspace.agent import core
    from cyberspace.agent.llm import LLMConfig
    from cyberspace.modules.base import Tool, ToolRegistry

    called = []
    registry = ToolRegistry()
    registry.register(Tool("iceberg.check", "test", {"type": "object", "properties": {}},
                           lambda: called.append(True)))
    monkeypatch.setattr(core, "get_provider", lambda cfg: object())
    agent = core.Agent(LLMConfig(), registry=registry, include_project_tools=False, scope="iceberg")
    result = agent._execute(SimpleNamespace(name="robodaddy.train", arguments={}))
    assert "outside" in result
    assert not called


def test_robodaddy_keys_store_only_metadata(tmp_path, monkeypatch):
    import cyberspace.config as config
    import cyberspace.credentials as credentials
    from cyberspace.platforms.robodaddy import registry

    secrets = {}
    root = tmp_path / "robodaddy"
    monkeypatch.setattr(config, "MODULES_DIR", tmp_path)
    monkeypatch.setattr(registry, "T_DIR", root)
    monkeypatch.setattr(registry, "MODELS_FILE", root / "models.json")
    monkeypatch.setattr(registry, "KEYS_FILE", root / "keys.json")
    monkeypatch.setattr(registry, "LOCK_FILE", root / ".registry.lock")
    monkeypatch.setattr(credentials, "set_secret", lambda name, value: secrets.update({name: value}))
    monkeypatch.setattr(credentials, "get_secret", lambda name, env_var="": secrets.get(name, ""))
    monkeypatch.setattr(credentials, "delete_secret", lambda name: secrets.pop(name, None))

    key = registry.issue_key("model", "http://localhost/v1")
    raw = (root / "keys.json").read_text()
    assert key.key.startswith("rbd_")
    assert key.key not in raw
    assert key.prefix in raw
    assert registry.revoke_key(key.prefix) == 1
    assert not secrets


def test_detached_training_survives_launcher_exit(tmp_path):
    """Real subprocess: launcher exits, independent worker completes and persists done."""
    env = {**os.environ, "CYBERSPACE_HOME": str(tmp_path)}
    result = subprocess.run(
        [sys.executable, "-m", "cyberspace", "robodaddy", "train", "general",
         "--success-criterion", "All integration-test jobs complete and evaluation artifacts exist"],
        cwd=Path(__file__).resolve().parents[1], env=env, capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, result.stderr
    assert "may close this terminal" in result.stdout.lower()
    models_file = tmp_path / "modules" / "robodaddy" / "models.json"
    deadline = time.time() + 20
    status = ""
    while time.time() < deadline:
        if models_file.exists():
            records = json.loads(models_file.read_text())
            status = records[0]["status"] if records else ""
            if status == "trained-not-evaluated":
                break
        time.sleep(0.2)
    assert status == "trained-not-evaluated"
    progress = tmp_path / "modules" / "robodaddy" / "jobs" / records[0]["name"] / "progress.jsonl"
    assert '"stage": "done"' in progress.read_text()


def test_paid_dispatch_supplies_training_bootstrap(tmp_path, monkeypatch):
    import cyberspace.config as config
    from cyberspace.platforms.robodaddy import registry, train
    from cyberspace.platforms.robodaddy.plan import build_plan
    from cyberspace.platforms.robodaddy.parameters import profile

    root = tmp_path / "robodaddy"
    monkeypatch.setattr(config, "MODULES_DIR", tmp_path)
    monkeypatch.setattr(registry, "T_DIR", root)
    monkeypatch.setattr(registry, "MODELS_FILE", root / "models.json")
    monkeypatch.setattr(registry, "KEYS_FILE", root / "keys.json")
    monkeypatch.setattr(registry, "LOCK_FILE", root / ".registry.lock")
    monkeypatch.setattr(train, "JOBS_DIR", root / "jobs")
    captured = {}

    class Vast:
        def rent(self, offer, **kwargs):
            captured.update(kwargs)
            return {"instance_id": 42}

    import cyberspace.platforms.robodaddy.vast as vast
    monkeypatch.setattr(vast, "VastClient", Vast)
    params = profile("custom_blank")
    params.success_criteria = ["Every paid-dispatch test receives a valid bootstrap script"]
    plan = build_plan("general", dataset_id="databricks/databricks-dolly-15k",
                      parameters=params)
    model = train.run_training(plan, dry_run=False, vast_offer_id=123)
    assert model.status == "training"
    assert "base64 -d" in captured["onstart"]
    assert "nohup python" in captured["onstart"]


def test_gated_data_is_blocked_before_paid_rental(tmp_path, monkeypatch):
    import cyberspace.config as config
    from cyberspace.platforms.robodaddy import registry, train
    from cyberspace.platforms.robodaddy.plan import build_plan
    from cyberspace.platforms.robodaddy.parameters import profile

    root = tmp_path / "robodaddy"
    monkeypatch.setattr(config, "MODULES_DIR", tmp_path)
    monkeypatch.setattr(registry, "T_DIR", root)
    monkeypatch.setattr(registry, "MODELS_FILE", root / "models.json")
    monkeypatch.setattr(registry, "KEYS_FILE", root / "keys.json")
    monkeypatch.setattr(registry, "LOCK_FILE", root / ".registry.lock")
    monkeypatch.setattr(train, "JOBS_DIR", root / "jobs")

    class Vast:
        def rent(self, *args, **kwargs):
            raise AssertionError("gated data must be rejected before rental")

    import cyberspace.platforms.robodaddy.vast as vast
    monkeypatch.setattr(vast, "VastClient", Vast)
    params = profile("custom_blank")
    params.success_criteria = ["Zero GPU rentals occur before gated-data rejection in the test"]
    plan = build_plan("offensive_pentest", dataset_id="trendmicro-ailab/Primus-Instruct",
                      parameters=params)
    model = train.run_training(plan, dry_run=False, vast_offer_id=123)
    assert model.status == "planned"