"""Tests for the guided start flow: dataset refresh, AI recommendation, GPU compare."""
from __future__ import annotations

import json


def _fake_recent_client(rows):
    class Response:
        def __init__(self, payload):
            self._payload = payload
        def raise_for_status(self):
            pass
        def json(self):
            return self._payload
    class Client:
        def __init__(self, *a, **k):
            self.rows = rows
        def get(self, url, params):
            return Response(self.rows)
    return Client()


def test_refresh_caches_latest_datasets(tmp_path, monkeypatch):
    import cyberspace.config as config
    import cyberspace.platforms.robodaddy.refresh as refresh
    monkeypatch.setattr(config, "MODULES_DIR", tmp_path)
    monkeypatch.setattr(refresh, "CACHE_FILE", tmp_path / "latest.json")
    client = _fake_recent_client([
        {"id": "owner/fresh", "lastModified": "2026-07-20T00:00:00Z",
         "downloads": 9, "likes": 1, "tags": ["license:apache-2.0"]},
    ])
    cached = refresh.refresh_datasets_cache(client=client)
    assert cached and cached[0]["id"] == "owner/fresh"
    assert refresh.cache_info()["count"] == 1
    latest = refresh.latest_datasets()
    assert latest[0]["source"] == "huggingface-recent"


def test_discover_recent_sorts_by_last_modified():
    from cyberspace.platforms.robodaddy.discovery import discover_recent_datasets
    rows = [
        {"id": "a/old", "lastModified": "2020-01-01T00:00:00Z", "tags": []},
        {"id": "a/new", "lastModified": "2026-07-01T00:00:00Z", "tags": []},
        {"id": "a/mid", "lastModified": "2024-01-01T00:00:00Z", "tags": []},
    ]
    found = discover_recent_datasets(limit=5, client=_fake_recent_client(rows))
    assert [d["id"] for d in found[:3]] == ["a/new", "a/mid", "a/old"]


def test_heuristic_recommend_tunes_for_cyber_multiturn():
    from cyberspace.platforms.robodaddy.parameters import profile
    from cyberspace.platforms.robodaddy.recommend import heuristic_recommend
    p = profile("cyber_redteam")
    rec = heuristic_recommend("cyber red team attack path multi-turn", p)
    assert rec.max_seq_len == 4096
    assert rec.lora_r == 32
    assert rec.optimizer == "paged_adamw_8bit"


def test_ai_recommend_parses_and_applies(monkeypatch):
    from cyberspace.platforms.robodaddy import recommend as R
    from cyberspace.platforms.robodaddy.parameters import profile

    class Resp:
        text = json.dumps({"epochs": 7, "max_seq_len": 8192, "lora_r": 64,
                           "optimizer": "paged_adamw_8bit"})
    class FakeProvider:
        def chat(self, messages, tools):
            return Resp()
    monkeypatch.setattr(R, "_provider", lambda: (FakeProvider(), None))

    p = profile("custom_blank")
    rec = R.recommend_parameters("a coding assistant", p, [])
    assert rec.epochs == 7 and rec.max_seq_len == 8192 and rec.lora_r == 64


def test_ai_recommend_rejects_invalid_base_model(monkeypatch):
    from cyberspace.platforms.robodaddy import recommend as R
    from cyberspace.platforms.robodaddy.parameters import profile

    class Resp:
        text = json.dumps({"base_model": "not-a-real-model", "epochs": 5})
    class FakeProvider:
        def chat(self, messages, tools):
            return Resp()
    monkeypatch.setattr(R, "_provider", lambda: (FakeProvider(), None))
    p = profile("custom_blank")
    rec = R.recommend_parameters("x", p, [])
    # invalid base model dropped; valid epoch applied
    assert rec.epochs == 5
    assert rec.base_model in ("", "qwen2.5-7b")


def test_enance_ai_changes_with_reasons(monkeypatch):
    from cyberspace.platforms.robodaddy import recommend as R
    from cyberspace.platforms.robodaddy.parameters import profile

    class Resp:
        text = json.dumps({"max_seq_len": 6144, "reasons": ["long multi-turn reasoning"]})
    class FakeProvider:
        def chat(self, messages, tools):
            return Resp()
    monkeypatch.setattr(R, "_provider", lambda: (FakeProvider(), None))
    p = profile("cyber_redteam")
    enhanced, reasons = R.enhance_parameters(p, "You reason through multi-turn attack paths")
    assert enhanced.max_seq_len == 6144
    assert reasons == ["long multi-turn reasoning"]


def test_compare_gpus_and_pick_best():
    from cyberspace.platforms.robodaddy.gpus import compare_gpus, pick_best_gpu
    rows = compare_gpus(8, "qlora", 50000, 3, 2048)
    assert rows  # compatible GPUs exist for an 8B QLoRA
    # Rows are sorted cheapest-total first.
    assert rows[0]["cost_mid"] <= rows[-1]["cost_mid"]
    best = pick_best_gpu(8, "qlora", 50000, 3, 2048)
    assert best == rows[0]["gpu"]


def test_start_and_latest_cli_commands_exist():
    from cyberspace.modules.registry import discover_and_load
    from cyberspace.modules.base import TOOL_REGISTRY
    discover_and_load()
    # CLI commands are built via the typer app; verify it builds with the new cmds.
    from cyberspace.platforms.robodaddy.cli import build_robodaddy_cli
    from rich.console import Console
    app = build_robodaddy_cli(Console())
    names = {c.name for c in app.registered_commands}
    assert "start" in names and "latest" in names
