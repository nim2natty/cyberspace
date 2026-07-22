"""Regression tests for the Cyber Kill Chain workspace."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from cyberspace.agent.llm import (
    AgentResponse, LLMConfig, ProviderError, ToolCall, _anthropic_messages,
    _anthropic_tool_name, chat_with_failover,
)
from cyberspace.swarm import KILL_CHAIN, detect_stage


class KillChainTests(unittest.TestCase):
    def test_seven_chronological_stages(self):
        self.assertEqual([s.phase for s in KILL_CHAIN], list(range(1, 8)))
        self.assertEqual([s.display for s in KILL_CHAIN], [
            "Reconnaissance", "Weaponization", "Delivery", "Exploitation",
            "Installation", "Command & Control (C2)", "Actions on Objectives",
        ])
        self.assertEqual(detect_stage("find devices on my local network"), "recon")
        self.assertEqual(detect_stage("write up the findings"), "objectives")

    def test_anthropic_tool_ids_are_preserved(self):
        converted = _anthropic_messages([
            {"role": "assistant", "content": "", "tool_calls": [{
                "id": "tool-7", "function": {"name": "airbender.chain",
                "arguments": '{"pipeline":"local-recon"}'}}]},
            {"role": "tool", "name": "airbender.chain", "tool_call_id": "tool-7",
             "content": "three hosts"},
        ])
        self.assertEqual(converted[0]["content"][0]["id"], "tool-7")
        self.assertEqual(converted[1]["content"][0]["tool_use_id"], "tool-7")

    def test_anthropic_tool_name_is_native_and_stable(self):
        alias = _anthropic_tool_name("robodaddy.train")
        self.assertNotIn(".", alias)
        self.assertEqual(alias, _anthropic_tool_name("robodaddy.train"))
        self.assertLessEqual(len(alias), 64)

    def test_model_failover_keeps_transcript(self):
        class FakeProvider:
            def __init__(self):
                self.cfg = LLMConfig(provider="openai", model="broken", base_url="http://x")
                self.seen = []
            def chat(self, messages, tools):
                self.seen.append((self.cfg.model, messages))
                if self.cfg.model == "broken":
                    raise ProviderError("model not found (HTTP 404)")
                return AgentResponse(text="continued")

        provider = FakeProvider()
        transcript = [{"role": "user", "content": "keep this objective"}]
        with patch("cyberspace.agent.llm._available_models", return_value=["broken", "working"]):
            response = chat_with_failover(provider, transcript, [])
        self.assertEqual(response.text, "continued")
        self.assertEqual(provider.cfg.model, "working")
        self.assertIs(provider.seen[1][1], transcript)

    def test_project_context_is_scoped(self):
        import cyberspace.projects as projects
        root = Path(tempfile.mkdtemp())
        with patch.object(projects, "PROJECTS_DIR", root / "projects"), \
             patch.object(projects, "ACTIVE_FILE", root / "active"):
            projects.create("lab-one")
            projects.add_prompt("lab-one", "scan 10.0.0.0/24", "found a router")
            projects.create("lab-two")
            projects.add_prompt("lab-two", "inspect web app", "port 443")
            projects.set_active("lab-one")
            context = projects.context_block()
            self.assertIn("scan 10.0.0.0/24", context)
            self.assertNotIn("inspect web app", context)

    def test_local_recon_merges_multiple_sources(self):
        from cyberspace.platforms.airbender import chain
        with patch.object(chain, "_tool_ping_sweep", return_value="10.0.0.2"), \
             patch.object(chain, "_tool_netdiscover", return_value="10.0.0.3"), \
             patch.object(chain, "_tool_arp_scan", return_value="10.0.0.2 10.0.0.4"):
            report = chain._tool_local_recon("10.0.0.0/24")
        self.assertIn("3 discovery methods", report)
        self.assertIn("3 unique IPs", report)
        self.assertIn("10.0.0.4", report)

    def test_nmap_expands_discovered_hosts(self):
        from cyberspace.platforms.airbender import chain
        class Result:
            def text(self): return "ok"
        with patch.object(chain, "is_available", return_value=True), \
             patch.object(chain, "run", return_value=Result()) as run:
            chain._tool_nmap("10.0.0.2 10.0.0.3", "--top-ports 10")
        self.assertEqual(run.call_args.args[1][-2:], ["10.0.0.2", "10.0.0.3"])


if __name__ == "__main__":
    unittest.main()