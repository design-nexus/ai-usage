#!/usr/bin/env python3
"""Contract and Claude fixture tests for the unified scanner."""
import importlib.util
import json
import os
import subprocess
import tempfile
import sys
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).parents[1] / "scripts"

class ScannerTests(unittest.TestCase):
    def run_scanner(self, provider, env=None):
        run = subprocess.run([sys.executable, SCRIPTS / "usage_scanner.py", provider], text=True,
            capture_output=True, check=True, env=env)
        return json.loads(run.stdout)

    def test_unavailable_cli_is_hidden(self):
        env = os.environ.copy(); env["PATH"] = "/definitely/not/a/bin"
        data = self.run_scanner("claude", env)
        self.assertFalse(data["available"])
        self.assertEqual(data["quotaGroups"], [])
        self.assertIn("not installed", data["usageStatusText"])

    def test_claude_transcript_is_local_usage_not_quota(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp) / ".claude" / "projects" / "project"
            base.mkdir(parents=True)
            (base / "session.jsonl").write_text(
                '{"timestamp":"2026-09-20T12:00:00Z","message":{"role":"user","content":"Fix the widget"}}\n'
                '{"message":{"role":"assistant","model":"claude-sonnet","usage":{"input_tokens":120,"output_tokens":30},"content":[{"type":"tool_use","name":"Read"}]}}\n')
            env = os.environ.copy(); env["CLAUDE_CONFIG_DIR"] = str(Path(temp) / ".claude")
            run = subprocess.run([sys.executable, SCRIPTS / "claude_usage_scanner.py"], text=True, capture_output=True, check=True, env=env)
            data = json.loads(run.stdout)
            self.assertEqual(data["quotaGroups"], [])
            self.assertEqual(data["todayTotalTokens"], 150)
            self.assertEqual(data["recentSessions"][0]["model"], "claude-sonnet")
            self.assertEqual(data["toolUsage"]["Read"], 1)
            self.assertEqual(data["modelList"][0]["name"], "claude-sonnet")
            self.assertEqual(sum(day["messageCount"] for day in data["recentDays"]), 1)
            self.assertEqual(len(data["recentDays"]), 7)
            self.assertEqual(data["quotaNote"], "Claude quota is not estimated.")

    def test_copilot_events_are_local_usage_not_quota(self):
        with tempfile.TemporaryDirectory() as temp:
            home = Path(temp)
            session_id = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
            events = home / "session-state" / session_id / "events.jsonl"
            events.parent.mkdir(parents=True)
            events.write_text(
                '{"type":"session.start","data":{"sessionId":"%s","startTime":"2026-09-21T15:00:00Z","context":{"cwd":"/tmp/work"}}}\n'
                '{"type":"user.message","data":{"content":"Fix the panel"}}\n'
                '{"type":"session.shutdown","data":{"totalPremiumRequests":2,"modelMetrics":{"gpt-4o":{"usage":{"inputTokens":10,"outputTokens":5,"cacheReadTokens":1,"cacheWriteTokens":0},"requests":{"count":1}}},"codeChanges":{"linesAdded":3,"linesRemoved":1,"filesModified":1}}}\n'
                % session_id)
            env = os.environ.copy()
            env["COPILOT_HOME"] = str(home)
            env["COPILOT_USAGE_SKIP_QUOTA"] = "1"
            run = subprocess.run([sys.executable, SCRIPTS / "copilot_usage_scanner.py"], text=True, capture_output=True, check=True, env=env)
            data = json.loads(run.stdout)
            self.assertEqual(data["quotaGroups"], [])
            self.assertEqual(data["totalPrompts"], 1)
            self.assertEqual(data["modelList"][0]["name"], "gpt-4o")
            self.assertEqual(data["premiumRequests"], 2)
            self.assertEqual(len(data["recentDays"]), 7)
            self.assertEqual(data["recentSessions"][0]["workspace"], "/tmp/work")
            self.assertEqual(data["codeChanges"]["filesModified"], 1)
            self.assertFalse(data["canKill"])

    def test_cursor_transcript_and_meta(self):
        with tempfile.TemporaryDirectory() as temp:
            data_home = Path(temp) / "cursor"
            config_home = Path(temp) / "config"
            session_id = "0d42a8e3-a2e3-4bc1-b69d-cf1ba49fe2a0"
            chat = config_home / "chats" / "workspacehash" / session_id
            chat.mkdir(parents=True)
            (chat / "meta.json").write_text(json.dumps({
                "schemaVersion": 1,
                "createdAtMs": 1758450000000,
                "updatedAtMs": 1758451000000,
                "cwd": "/home/ken/Work",
                "hasConversation": True,
            }))
            connection = __import__("sqlite3").connect(chat / "store.db")
            connection.execute("CREATE TABLE meta (id TEXT, title TEXT, model TEXT)")
            connection.execute("INSERT INTO meta VALUES (?, ?, ?)", (session_id, "Widget fix", "gpt-5"))
            connection.commit()
            connection.close()
            transcript = data_home / "projects" / "home-ken-Work" / "agent-transcripts" / session_id / f"{session_id}.jsonl"
            transcript.parent.mkdir(parents=True)
            transcript.write_text(
                '{"role":"user","message":{"role":"user","content":"hello"}}\n'
                '{"role":"assistant","message":{"role":"assistant","model":"gpt-5","content":[{"type":"tool_use","name":"Read","input":{}}]}}\n')
            env = os.environ.copy()
            env["CURSOR_DATA_HOME"] = str(data_home)
            env["CURSOR_CONFIG_HOME"] = str(config_home)
            env["CURSOR_USAGE_SKIP_ABOUT"] = "1"
            env["CURSOR_USAGE_SKIP_QUOTA"] = "1"
            run = subprocess.run([sys.executable, SCRIPTS / "cursor_usage_scanner.py"], text=True, capture_output=True, check=True, env=env)
            data = json.loads(run.stdout)
            self.assertEqual(data["quotaGroups"], [])
            self.assertEqual(data["totalPrompts"], 1)
            self.assertEqual(data["modelList"][0]["name"], "gpt-5")
            self.assertEqual(data["toolUsage"]["Read"], 1)
            self.assertEqual(data["recentSessions"][0]["workspace"], "/home/ken/Work")
            self.assertEqual(data["recentSessions"][0]["title"], "Widget fix")
            self.assertEqual(len(data["recentDays"]), 7)
            self.assertFalse(data["canKill"])

    def test_new_providers_hide_when_cli_missing(self):
        env = os.environ.copy()
        env["PATH"] = "/definitely/not/a/bin"
        for provider in ("copilot", "cursor"):
            data = self.run_scanner(provider, env)
            self.assertFalse(data["available"])
            self.assertEqual(data["quotaGroups"], [])
            self.assertEqual(len(data["recentDays"]), 7)
            self.assertIn("not installed", data["usageStatusText"])

    def load_scanner(self, name):
        spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_copilot_free_plan_quota_buckets(self):
        module = self.load_scanner("copilot_usage_scanner")
        groups, tier = module.quota_from_copilot_user({
            "access_type_sku": "free_limited_copilot",
            "copilot_plan": "individual",
            "quota_snapshots": {
                "chat": {"entitlement": 200, "percent_remaining": 96.6, "remaining": 193, "unlimited": False},
                "completions": {"entitlement": 2000, "percent_remaining": 99.4, "remaining": 1989, "unlimited": False},
                "premium_interactions": {"entitlement": 0, "percent_remaining": 0, "remaining": 0, "unlimited": False},
            },
        })
        self.assertEqual(tier, "Free")
        labels = [bucket["label"] for bucket in groups[0]["buckets"]]
        self.assertEqual(labels, ["Chat", "Completions"])
        self.assertEqual(groups[0]["buckets"][0]["remainingPercent"], 97)
        self.assertIn("193 of 200", groups[0]["buckets"][0]["forecastText"])

    def test_cursor_free_plan_quota_bucket(self):
        module = self.load_scanner("cursor_usage_scanner")
        groups, tier = module.quota_from_cursor_period(
            {
                "billingCycleEnd": "1791627544569",
                "planUsage": {"totalPercentUsed": 0, "autoPercentUsed": 0, "apiPercentUsed": 0},
                "displayMessage": "You've used 0% of your included usage",
            },
            {"planInfo": {"planName": "Free"}},
        )
        self.assertEqual(tier, "Free")
        self.assertEqual(len(groups[0]["buckets"]), 1)
        self.assertEqual(groups[0]["buckets"][0]["label"], "Included usage")
        self.assertEqual(groups[0]["buckets"][0]["remainingPercent"], 100)
        self.assertTrue(groups[0]["buckets"][0]["resetTime"])

    def test_result_contract_keys(self):
        # An unavailable provider is deterministic and still exercises the full contract.
        env = os.environ.copy(); env["PATH"] = ""
        data = self.run_scanner("grok", env)
        for key in ("providerId", "available", "active", "quotaGroups", "recentSessions", "error", "display"):
            self.assertIn(key, data)

if __name__ == "__main__": unittest.main()
