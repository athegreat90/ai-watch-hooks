import json
import subprocess
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

received = []


class Receiver(BaseHTTPRequestHandler):
    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        received.append((self.path, self.headers.get("X-Monitor-Key"), body["status"]))
        self.send_response(200)
        self.end_headers()


with HTTPServer(("127.0.0.1", 0), Receiver) as server:
    thread = threading.Thread(target=server.serve_forever)
    thread.start()
    try:
        with tempfile.TemporaryDirectory() as folder:
            config = Path(folder) / "config.local.json"
            config.write_text(json.dumps({
                "url": f"http://127.0.0.1:{server.server_port}", "token": "fixture",
            }), encoding="utf-8")
            config.chmod(0o644)
            event = {"session_id": "ci", "hook_event_name": "BeforeAgent", "cwd": "/ci"}
            result = subprocess.run(
                ["docker", "run", "--rm", "-i", "--platform", f"linux/{sys.argv[2]}",
                 "--network", "host", "--mount",
                 f"type=bind,source={config},target=/app/config.local.json,readonly",
                 sys.argv[1], "gemini"],
                input=json.dumps(event), text=True, capture_output=True, timeout=60, check=True,
            )
    finally:
        server.shutdown()
        thread.join()

if result.stdout.strip() != "{}" or received != [("/api/events", "fixture", "working")]:
    raise SystemExit("Hook container did not forward the expected event.")
