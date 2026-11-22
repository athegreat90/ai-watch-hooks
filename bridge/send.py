import argparse
import time

from hook import send

parser = argparse.ArgumentParser(description="Publish an explicit AI Watch test event")
parser.add_argument("--status", choices=["working", "needs_attention", "done", "idle", "error"], required=True)
parser.add_argument("--agent", choices=["Codex", "Claude Code", "Gemini CLI", "GitHub Copilot CLI", "Antigravity"], default="Codex")
args = parser.parse_args()
status = send({"agent": args.agent, "project": "AI Watch test", "session_id": "manual-test",
               "status": args.status, "detail": "Synthetic test event", "timestamp": time.time()})
if status != 200:
    raise SystemExit(f"Backend rejected test event with HTTP {status}")
print("Test event accepted.")
