from __future__ import annotations

import json
from pathlib import Path


def test_iceberg_legacy_e_state_is_merged(tmp_path, monkeypatch):
    import cyberspace.config as config
    from cyberspace.platforms.iceberg.secure import security

    modules = tmp_path / "modules"
    old = modules / "iceberg" / "e"
    (old / "investigations").mkdir(parents=True)
    (old / "security.json").write_text(json.dumps({"mode": "dark"}))
    (old / "investigations" / "investigation_old.json").write_text("{}")
    monkeypatch.setattr(config, "MODULES_DIR", modules)
    monkeypatch.setattr(security, "ICEBERG_DIR", modules / "iceberg")
    monkeypatch.setattr(security, "LEGACY_E_DIR", old)
    monkeypatch.setattr(security, "SECURITY_FILE", modules / "iceberg" / "security.json")

    loaded = security.SecurityConfig.load()
    assert loaded.mode == "dark"
    assert not old.exists()
    assert (modules / "iceberg" / "investigations" / "investigation_old.json").exists()


def test_mullvad_controls_use_argument_lists(monkeypatch):
    from cyberspace.host import RunResult
    from cyberspace.platforms.iceberg import privacy

    calls = []
    monkeypatch.setattr(privacy, "is_available", lambda name: name == "mullvad")
    monkeypatch.setattr(privacy, "run", lambda name, args, timeout=0: (
        calls.append((name, args)) or RunResult(True, "ok", "", 0)))
    assert privacy.mullvad_action("lockdown-on") == "ok"
    assert privacy.mullvad_dns(True) == "ok"
    assert calls == [("mullvad", ["lockdown-mode", "set", "on"]),
                     ("mullvad", ["dns", "set", "default", "--block-ads",
                                  "--block-trackers", "--block-malware"])]


def test_audit_always_returns_actionable_findings(monkeypatch):
    from cyberspace.platforms.iceberg import privacy

    monkeypatch.setattr(privacy, "mullvad_status", lambda: "Disconnected")
    monkeypatch.setattr(privacy, "dns_status", lambda: "DNS servers: 8.8.8.8")
    findings = privacy.audit()
    assert findings
    assert all(f.solution for f in findings)
    assert any(f.area == "network" for f in findings)