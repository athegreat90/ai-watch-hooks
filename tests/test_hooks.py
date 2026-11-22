import json
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
import unittest
from pathlib import Path
from unittest.mock import patch
from bridge import hook, install, limits

class HooksTests(unittest.TestCase):
    def test_installer_preserves_other_settings(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as directory:
            home = Path(directory)
            config = home / ".claude" / "settings.json"
            config.parent.mkdir()
            original = {"hooks": {"Stop": [{"hooks": [{"command": "old-hook"}]}]}, "theme": "light"}
            config.write_text(json.dumps(original), encoding="utf-8")
            with (patch.object(install.Path, "home", return_value=home),
                  patch.object(install.shutil, "which", return_value="claude"),
                  patch.object(install.subprocess, "run",
                               return_value=install.subprocess.CompletedProcess([], 0, "2.1.329"))):
                install.install("claude", False)
                first = config.read_bytes()
                install.install("claude", False)
                self.assertEqual(first, config.read_bytes())
                self.assertEqual(len(list(config.parent.glob("*.backup-*"))), 1)
                install.install("claude", True)
                self.assertEqual(json.loads(config.read_bytes()), original)

    def test_delivery_to_private_api(self):
        events = []

        class Receiver(BaseHTTPRequestHandler):
            def do_POST(self):
                payload = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                events.append((self.path, self.headers["X-Monitor-Key"], payload["status"]))
                self.send_response(200)
                self.end_headers()

            def log_message(self, *args):
                pass

        with HTTPServer(("127.0.0.1", 0), Receiver) as server:
            thread = threading.Thread(target=server.serve_forever)
            thread.start()
            try:
                with tempfile.TemporaryDirectory(prefix="ai watch ") as directory:
                    config = Path(directory) / "config.local.json"
                    config.write_text(json.dumps({"url": f"http://127.0.0.1:{server.server_port}",
                                                  "token": "fixture"}), encoding="utf-8")
                    with patch.object(hook, "CONFIG", config):
                        self.assertEqual(hook.send({"status": "working"}), 200)
                    command = install.shlex.join(["/opt/ai watch/python", str(config), "codex"])
                    self.assertEqual(install.shlex.split(command)[1], str(config))
            finally:
                server.shutdown()
                thread.join()
        self.assertEqual(events, [("/api/events", "fixture", "working")])

    def test_hook_privacy_and_mapping(self):
        info = {"session_id": "id", "cwd": r"C:\private\workspace",
                "hook_event_name": "AfterTool", "prompt": "private prompt",
                "tool_response": {"error": "secret error text"}}
        event = hook.to_event(info, "gemini")
        self.assertEqual((event["status"], event["project"]), ("error", "workspace"))
        for value in ("private", "secret", "tool_response"):
            self.assertNotIn(value, json.dumps(event))
        self.assertIsNone(hook.to_event({"hook_event_name": "Stop"}, "codex"))

    def test_new_agents_mapping(self):
        copilot = hook.to_event({"hook_event_name": "ErrorOccurred", "session_id": "s", "cwd": "/w/app"}, "copilot")
        self.assertEqual((copilot["agent"], copilot["status"], copilot["project"]),
                         ("GitHub Copilot CLI", "error", "app"))
        info = {"conversationId": "c", "workspacePaths": [r"C:\w\proj"], "fullyIdle": True}
        event = hook.to_event(info, "antigravity", "Stop")
        self.assertEqual((event["agent"], event["status"], event["project"]), ("Antigravity", "done", "proj"))
        self.assertIsNone(hook.to_event({**info, "fullyIdle": False}, "antigravity", "Stop"))
        self.assertEqual(hook.to_event(info, "antigravity", "PreToolUse")["status"], "working")

    def test_limits_parsing(self):
        claude = limits.claude_payload({"rate_limits": {"five_hour": {"used_percentage": 23.5, "resets_at": 5},
                                                        "seven_day": {"used_percentage": 41, "resets_at": 9}}})
        self.assertEqual((claude["agent"], claude["weekly"]["used_pct"]), ("Claude Code", 41))
        self.assertIsNone(limits.claude_payload({"rate_limits": {"five_hour": {}}}))
        line = json.dumps({"payload": {"rate_limits": {"primary": {"used_percent": 97.0, "resets_at": 1},
                                                      "secondary": {"used_percent": 47.0, "resets_at": 2}}}})
        null = json.dumps({"payload": {"rate_limits": {"primary": None, "secondary": None}}})
        codex = limits.codex_payload(line + chr(10) + null)  # newest line has no data: fall back to older one
        self.assertEqual((codex["agent"], codex["five_hour"]["used_pct"]), ("Codex", 97.0))
        self.assertIsNone(limits.codex_payload(null))
        quota = {"quota": {"gemini-5h": {"remaining_fraction": 0.75, "reset_in_seconds": 100},
                           "gemini-weekly": {"remaining_fraction": 0.1, "reset_in_seconds": 500}}}
        agy = limits.antigravity_payload(quota, now=1000)
        self.assertEqual((agy["agent"], agy["five_hour"]["used_pct"], agy["weekly"]["used_pct"]), ("Antigravity", 25, 90))
        self.assertEqual((agy["five_hour"]["resets_at"], agy["weekly"]["resets_at"]), (1100, 1500))
        self.assertIsNone(limits.antigravity_payload({"quota": {"gemini-5h": {"remaining_fraction": 1}}}))
        self.assertIsNone(limits.antigravity_payload({}))

    def test_dedicated_installers(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as directory:
            home = Path(directory)
            (home / ".copilot").mkdir()
            (home / ".gemini" / "config").mkdir(parents=True)
            cli = home / ".gemini" / "antigravity-cli" / "settings.json"
            cli.parent.mkdir()
            cli.write_text(json.dumps({"model": "x"}), encoding="utf-8")
            hooks = home / ".gemini" / "config" / "hooks.json"
            hooks.write_text(json.dumps({"other": {"Stop": []}}), encoding="utf-8")
            with patch.object(install.Path, "home", return_value=home):
                for agent in ("copilot", "antigravity"):
                    install.install(agent, False)
                    install.install(agent, False)  # idempotent
                copilot = json.loads((home / ".copilot" / "hooks" / "ai-watch.json").read_text())
                self.assertEqual(copilot["version"], 1)
                self.assertIn("PermissionRequest", copilot["hooks"])
                entry = json.loads(hooks.read_text())
                self.assertEqual(entry["other"], {"Stop": []})
                self.assertTrue(entry["ai-watch"]["Stop"][0]["command"].endswith("Stop"))
                self.assertEqual(entry["ai-watch"]["PreToolUse"][0]["matcher"], "*")
                self.assertEqual(len(list(hooks.parent.glob("hooks.json.backup-*"))), 1)
                settings = json.loads(cli.read_text())
                self.assertEqual(settings["model"], "x")
                self.assertIn("statusline.py", settings["statusLine"]["command"])
                for agent in ("copilot", "antigravity"):
                    install.install(agent, True)
                self.assertEqual(json.loads(hooks.read_text()), {"other": {"Stop": []}})
                self.assertEqual(json.loads(cli.read_text()), {"model": "x"})
                self.assertFalse((home / ".copilot" / "hooks" / "ai-watch.json").exists())

    def test_claude_statusline_registered_only_when_free(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as directory:
            home = Path(directory)
            config = home / ".claude" / "settings.json"
            config.parent.mkdir()
            config.write_text(json.dumps({"statusLine": {"type": "command", "command": "mine"}}), encoding="utf-8")
            with (patch.object(install.Path, "home", return_value=home),
                  patch.object(install.shutil, "which", return_value="claude"),
                  patch.object(install.subprocess, "run",
                               return_value=install.subprocess.CompletedProcess([], 0, "2.1.329"))):
                install.install("claude", False)
                self.assertEqual(json.loads(config.read_text())["statusLine"]["command"], "mine")
                install.install("claude", True)
                config.write_text("{}", encoding="utf-8")
                install.install("claude", False)
                self.assertIn("statusline.py", json.loads(config.read_text())["statusLine"]["command"])
                install.install("claude", True)
                self.assertNotIn("statusLine", json.loads(config.read_text()))


if __name__ == "__main__":
    unittest.main()
