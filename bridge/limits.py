"""Forward 5-hour and weekly usage limits to the AI Watch server. Fails silently."""
import json
import os
import tempfile
import time
from pathlib import Path

THROTTLE_SECONDS = 60
TAIL_BYTES = 256 * 1024


def _due(agent):
    stamp = Path(tempfile.gettempdir()) / f"ai-watch-limits-{agent.replace(' ', '-')}"
    try:
        if time.time() - stamp.stat().st_mtime < THROTTLE_SECONDS:
            return False
    except OSError:
        pass
    stamp.touch()
    return True


def _window(item, used_key):
    used, resets = item.get(used_key), item.get("resets_at")
    if type(used) not in (int, float) or type(resets) not in (int, float):
        return None
    return {"used_pct": min(100, max(0, used)), "resets_at": resets}


def claude_payload(info):
    """Statusline JSON -> limits payload (rate_limits.five_hour / seven_day)."""
    limits = info.get("rate_limits")
    if not isinstance(limits, dict):
        return None
    five = _window(limits.get("five_hour") or {}, "used_percentage")
    week = _window(limits.get("seven_day") or {}, "used_percentage")
    return {"agent": "Claude Code", "five_hour": five, "weekly": week} if five and week else None


def antigravity_payload(info, now=None):
    """Antigravity statusLine JSON -> limits payload (quota.gemini-5h / gemini-weekly, remaining_fraction)."""
    quota, now = info.get("quota"), now if now is not None else time.time()
    if not isinstance(quota, dict):
        return None
    windows = []
    for name in ("gemini-5h", "gemini-weekly"):
        item = quota.get(name)
        left = item.get("remaining_fraction") if isinstance(item, dict) else None
        secs = item.get("reset_in_seconds") if isinstance(item, dict) else None
        if type(left) not in (int, float) or type(secs) not in (int, float):
            return None
        windows.append(_window({"used": (1 - left) * 100, "resets_at": now + secs}, "used"))
    return {"agent": "Antigravity", "five_hour": windows[0], "weekly": windows[1]} if all(windows) else None


def codex_payload(text):
    """Newest token_count line with rate_limits.primary (5h) and .secondary (weekly)."""
    for line in reversed(text.splitlines()):
        if '"rate_limits"' not in line:
            continue
        try:
            found = json.loads(line)["payload"]["rate_limits"]
            five, week = _window(found["primary"], "used_percent"), _window(found["secondary"], "used_percent")
        except (ValueError, KeyError, TypeError, AttributeError):
            continue
        if five and week:
            return {"agent": "Codex", "five_hour": five, "weekly": week}
    return None


def _newest_codex_log():
    root = Path(os.environ.get("CODEX_HOME") or (Path.home() / ".codex")) / "sessions"
    logs = list(root.glob("*/*/*/rollout-*.jsonl"))
    return max(logs, key=lambda path: path.stat().st_mtime, default=None)


def _send(payload):
    try:  # late import: hook imports this module
        from bridge.hook import send
    except ImportError:  # executed as a script: bridge/ is sys.path[0]
        from hook import send
    send(payload, "/api/limits")


def report_codex():
    if not _due("Codex"):
        return
    log = _newest_codex_log()
    if not log:
        return
    with log.open("rb") as file:
        file.seek(max(0, log.stat().st_size - TAIL_BYTES))
        payload = codex_payload(file.read().decode("utf-8", "ignore"))
    if payload:
        _send(payload)


def report_status(info):
    """Called with a statusLine payload from Claude Code or Antigravity; returns the limits it found."""
    payload = claude_payload(info) or antigravity_payload(info)
    if payload and _due(payload["agent"]):
        _send(payload)
    return payload
