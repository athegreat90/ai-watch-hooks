"""Merge or remove AI Watch command hooks with settings backups."""
from __future__ import annotations

import argparse
import json
import os
import shlex
import shutil
import subprocess
import sys
from datetime import datetime
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
HOOK = HERE / "hook.py"
EVENTS = {
    "claude": ["SessionStart", "UserPromptSubmit", "PreToolUse", "PostToolUse", "PermissionRequest", "Notification", "PostToolUseFailure", "StopFailure", "Stop", "SessionEnd"],
    "codex": ["SessionStart", "UserPromptSubmit", "PreToolUse", "PostToolUse", "PermissionRequest", "Stop", "Interrupt", "SessionEnd"],
    "gemini": ["SessionStart", "BeforeAgent", "BeforeTool", "AfterTool", "Notification", "AfterAgent", "SessionEnd"],
}


def install(agent: str, uninstall: bool) -> None:
    path = {"claude": Path.home() / ".claude" / "settings.json",
            "codex": Path(os.environ.get("CODEX_HOME") or (Path.home() / ".codex")) / "hooks.json",
            "gemini": Path.home() / ".gemini" / "settings.json"}[agent]
    cli = shutil.which(agent) or shutil.which(agent + ".cmd")
    if not uninstall:
        if not cli:
            print(f"Skipped {agent}: CLI unavailable")
            return
        result = subprocess.run([cli, "--version"], capture_output=True, text=True, timeout=10)
        if result.returncode:
            raise RuntimeError(f"{agent} version check failed")
        print(f"{agent}: {result.stdout.strip()}")
    if uninstall and not path.exists():
        return
    raw = path.read_bytes() if path.exists() else b"{}"
    data = json.loads(raw.decode("utf-8-sig"))
    if not isinstance(data, dict) or not isinstance(data.get("hooks", {}), dict):
        raise ValueError(f"Unexpected JSON structure: {path}")
    hooks = data.setdefault("hooks", {})
    command = (subprocess.list2cmdline([sys.executable, str(HOOK), agent]) if os.name == "nt"
               else shlex.join([sys.executable, str(HOOK), agent]))
    suffix = (subprocess.list2cmdline([str(HOOK), agent]) if os.name == "nt"
              else shlex.join([str(HOOK), agent]))
    for event in dict.fromkeys([*hooks, *([] if uninstall else EVENTS[agent])]):
        groups = hooks.setdefault(event, [])
        if not isinstance(groups, list):
            raise ValueError(f"Invalid hooks.{event} in {path}")
        # Remove only our old handler; preserve any other handlers in mixed groups.
        preserved = []
        for group in groups:
            if not isinstance(group, dict) or not isinstance(group.get("hooks"), list):
                preserved.append(group)
                continue
            remaining = [h for h in group["hooks"] if not (
                isinstance(h, dict) and isinstance(h.get("command"), str)
                and h["command"].endswith(" " + suffix)
            )]
            if remaining:
                preserved.append({**group, "hooks": remaining})
        groups[:] = preserved
        if uninstall or event not in EVENTS[agent]:
            if not groups:
                hooks.pop(event, None)
            continue
        handler = {"type": "command", "command": command,
                   "timeout": 1500 if agent == "gemini" else 3}
        if agent == "claude":
            handler["async"] = True
        if agent == "gemini":
            handler["name"] = "ai-monitor"
        group = {"hooks": [handler]}
        if agent == "codex" and event == "SessionStart":
            group["matcher"] = "startup|resume|clear|fork"
        groups.append(group)
    if data == json.loads(raw.decode("utf-8-sig")):
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        backup = path.with_name(path.name + ".backup-" + datetime.now().strftime("%Y%m%d-%H%M%S-%f"))
        shutil.copy2(path, backup)
        print(f"Backup: {backup}")
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, delete=False) as file:
            temporary = Path(file.name)
            file.write(json.dumps(data, indent=2) + "\n")
        if path.exists() and path.read_bytes() != raw:
            raise RuntimeError("Settings changed during hook installation")
        temporary.replace(path)
    finally:
        if temporary and temporary.exists():
            temporary.unlink()
    print(f"Updated {agent}: {path}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--agent", choices=["all", "claude", "codex", "gemini"], default="all")
    parser.add_argument("--uninstall", action="store_true")
    args = parser.parse_args()
    wanted = (HERE.parent / ".python-version").read_text().strip()
    if not args.uninstall and ".".join(map(str, sys.version_info[:3])) != wanted:
        parser.error(f"Install and invoke Python {wanted} before registering hooks.")
    failures = []
    for agent in (EVENTS if args.agent == "all" else [args.agent]):
        try:
            install(agent, args.uninstall)
        except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
            print(f"{agent}: {error}", file=sys.stderr)
            failures.append(agent)
    if not args.uninstall:
        print("Restart the agent CLIs. Review and trust the monitor commands in Codex /hooks.")
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
