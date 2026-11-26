"""Forward allowlisted lifecycle metadata. Normal hook output is always neutral."""
import hashlib
import http.client
import ipaddress
import json
import ssl
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
    "ErrorOccurred": ("error", "Turn failed"),
    # Antigravity has no permission event; its hooks fire per model call and tool.
    "PreInvocation": ("working", "Turn started"),
}
AGENTS = {"codex": "Codex", "claude": "Claude Code", "gemini": "Gemini CLI",
          "copilot": "GitHub Copilot CLI", "antigravity": "Antigravity"}

def to_event(info, agent, event=None):
    # Antigravity payloads carry no event name (the installer passes it as argv) and use camelCase.
    name = info.get("hook_event_name") or event
    session = info.get("session_id") or info.get("conversationId")
    if agent == "antigravity" and name == "Stop" and info.get("fullyIdle") is False:
        return None
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
    if cwd is None and isinstance(info.get("workspacePaths"), list) and info["workspacePaths"]:
        cwd = info["workspacePaths"][0]
    project = cwd.replace(chr(92), "/").rstrip("/").rsplit("/", 1)[-1] if isinstance(cwd, str) else ""
    return {
        "session_id": hashlib.sha256(session.encode()).hexdigest(),
        "agent": AGENTS[agent],
        "project": (project or "Project")[:40], "status": state, "detail": detail,
        "timestamp": time.time(),
    }

def connect(url):
    """Return an unopened connection to a validated origin: https with a host name, or private IPv4 over http."""
    target = urlsplit(url)
    if target.username or target.path not in ("", "/") or not target.hostname:
        raise ValueError("Use a private IPv4 HTTP origin or an HTTPS origin")
    if target.scheme == "https":  # the default context verifies the certificate and host name
        return http.client.HTTPSConnection(target.hostname, target.port or 443, timeout=2,
                                           context=ssl.create_default_context())
    address = ipaddress.IPv4Address(target.hostname)
    private = address.is_loopback or any(address in ipaddress.IPv4Network(network) for network in
                                         ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16"))
    if target.scheme != "http" or not private:
        raise ValueError("Use a private IPv4 HTTP origin or an HTTPS origin")
    return http.client.HTTPConnection(str(address), target.port or 8765, timeout=0.5)

def send(event, path="/api/events"):
    config = json.loads(CONFIG.read_text(encoding="utf-8-sig"))
    connection = connect(config["url"])
    try:
        connection.request("POST", path, json.dumps(event), {
            "Content-Type": "application/json", "X-Monitor-Key": config["token"],
        })
        return connection.getresponse().status
    finally:
        connection.close()

if __name__ == "__main__":
    agent = sys.argv[1]
    try:
        event = to_event(json.loads(sys.stdin.buffer.read(1024 * 1024)), agent,
                         sys.argv[2] if len(sys.argv) > 2 else None)
        if event:
            send(event)
        if agent == "codex" and event:
            try:
                import limits  # the one-shot Docker image ships hook.py only
            except ImportError:
                limits = None
            if limits:
                limits.report_codex()
    except (OSError, ValueError, TypeError, KeyError, AttributeError, RecursionError, http.client.HTTPException):
        pass
    if agent == "gemini":
        print("{}")
