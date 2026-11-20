import json
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
import unittest
from pathlib import Path
from unittest.mock import patch
from bridge import hook, install

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


if __name__ == "__main__":
    unittest.main()
