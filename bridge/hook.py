"""Forward allowlisted lifecycle metadata. Normal hook output is always neutral."""
import hashlib
import http.client
import ipaddress
import json
import sys
import time
from pathlib import Path
from urllib.parse import urlsplit

CONFIG = Path(__file__).with_name("config.local.json")
STATES = {
    "SessionStart": ("idle", "Session opened"),
    "UserPromptSubmit": ("working", "Turn started"),
    "BeforeAgent": ("working", "Turn started"),
    "PreToolUse": ("working", "Tool running"),
    "BeforeTool": ("working", "Tool running"),
    "PostToolUse": ("working", "Tool returned"),
    "AfterTool": ("working", "Tool returned"),
    "PostToolUseFailure": ("error", "Tool failed"),
    "StopFailure": ("error", "Turn failed"),
    "PermissionRequest": ("needs_attention", "Permission requested"),
    "Stop": ("done", "Turn finished"),
    "AfterAgent": ("done", "Turn finished"),
    "SessionEnd": ("done", "Session closed"),
    "Interrupt": ("idle", "Turn interrupted"),
}

def to_event(info, agent):
    name = info.get("hook_event_name")
    session = info.get("session_id")
    if not isinstance(session, str) or not session:
        return None
    if name == "Notification":
        if info.get("notification_type") not in ("permission_prompt", "elicitation_dialog", "ToolPermission"):
            return None
        state, detail = "needs_attention", "Check the agent terminal"
    elif name in STATES:
        state, detail = STATES[name]
        result = info.get("tool_response")
        if agent == "gemini" and name == "AfterTool" and isinstance(result, dict) and result.get("error"):
            state, detail = "error", "Tool failed"
    else:
        return None
    cwd = info.get("cwd")
    project = cwd.replace(chr(92), "/").rstrip("/").rsplit("/", 1)[-1] if isinstance(cwd, str) else ""
    return {
        "session_id": hashlib.sha256(session.encode()).hexdigest(),
        "agent": {"codex": "Codex", "claude": "Claude Code", "gemini": "Gemini CLI"}[agent],
        "project": (project or "Project")[:40], "status": state, "detail": detail,
        "timestamp": time.time(),
    }

def send(event):
    config = json.loads(CONFIG.read_text(encoding="utf-8-sig"))
    target = urlsplit(config["url"])
    address = ipaddress.IPv4Address(target.hostname)
    private = address.is_loopback or any(address in ipaddress.IPv4Network(network) for network in
                                         ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16"))
    if target.scheme != "http" or not private or target.username or target.path not in ("", "/"):
        raise ValueError("Use a private IPv4 HTTP origin")
    connection = http.client.HTTPConnection(str(address), target.port or 8765, timeout=0.5)
    try:
        connection.request("POST", "/api/events", json.dumps(event), {
            "Content-Type": "application/json", "X-Monitor-Key": config["token"],
        })
        return connection.getresponse().status
    finally:
        connection.close()

if __name__ == "__main__":
    agent = sys.argv[1]
    try:
        event = to_event(json.loads(sys.stdin.buffer.read(1024 * 1024)), agent)
        if event:
            send(event)
    except (OSError, ValueError, TypeError, KeyError, AttributeError, RecursionError, http.client.HTTPException):
        pass
    if agent == "gemini":
        print("{}")
