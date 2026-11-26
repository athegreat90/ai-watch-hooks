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
STATUSLINE = HERE / "statusline.py"
EVENTS = {
    "claude": ["SessionStart", "UserPromptSubmit", "PreToolUse", "PostToolUse", "PermissionRequest", "Notification", "PostToolUseFailure", "StopFailure", "Stop", "SessionEnd"],
    "codex": ["SessionStart", "UserPromptSubmit", "PreToolUse", "PostToolUse", "PermissionRequest", "Stop", "Interrupt", "SessionEnd"],
    "gemini": ["SessionStart", "BeforeAgent", "BeforeTool", "AfterTool", "Notification", "AfterAgent", "SessionEnd"],
    "copilot": ["SessionStart", "UserPromptSubmit", "PreToolUse", "PostToolUse", "PostToolUseFailure", "PermissionRequest", "Notification", "ErrorOccurred", "Stop", "SessionEnd"],
    "antigravity": ["SessionStart", "PreInvocation", "PreToolUse", "PostToolUse", "Stop"],
}
NAME = "ai-watch"


def _fwd(part) -> str:
    # Claude Code runs hooks through Git Bash on Windows, which strips backslashes; Python accepts "/".
    return str(part).replace(chr(92), "/") if os.name == "nt" else str(part)


def _cmdline(*parts) -> str:
    parts = [_fwd(part) for part in parts]
    return subprocess.list2cmdline(parts) if os.name == "nt" else shlex.join(parts)


def _save(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        backup = path.with_name(path.name + ".backup-" + datetime.now().strftime("%Y%m%d-%H%M%S-%f"))
        shutil.copy2(path, backup)
        print(f"Backup: {backup}")
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(data, indent=2) + chr(10), encoding="utf-8")
    temporary.replace(path)
    print(f"Updated: {path}")


def _statusline(data: dict, uninstall: bool, label: str) -> None:
    """Own the statusLine key only when it is unset or already ours; limits come from it, not from hooks."""
    status = _cmdline(sys.executable, STATUSLINE)
    ours = {status, subprocess.list2cmdline([sys.executable, str(STATUSLINE)]) if os.name == "nt" else status}
    current = data.get("statusLine")
    mine = isinstance(current, dict) and current.get("command") in ours
    if uninstall and mine:
        del data["statusLine"]
    elif not uninstall and (current is None or mine):
        data["statusLine"] = {"type": "command", "command": status}
    elif not uninstall:
        print(f"{label} statusLine already set; usage limits stay off. See README to chain statusline.py.")


def install_dedicated(agent: str, uninstall: bool) -> None:
    """Copilot CLI and Antigravity read dedicated hook files, so we own our entry outright."""
    home = Path.home()
    if agent == "copilot":
        path, parent = home / ".copilot" / "hooks" / f"{NAME}.json", home / ".copilot"
    else:
        path, parent = home / ".gemini" / "config" / "hooks.json", home / ".gemini"
    if not parent.exists():
        print(f"Skipped {agent}: not installed")
        return
    if agent == "copilot":
        if uninstall:
            path.unlink(missing_ok=True)
            return
        handler = {"type": "command", "bash": shlex.join([_fwd(sys.executable), _fwd(HOOK), agent]),
                   "powershell": subprocess.list2cmdline([sys.executable, str(HOOK), agent]), "timeoutSec": 3}
        data = {"version": 1, "hooks": {event: [handler] for event in EVENTS[agent]}}
        if not path.exists() or json.loads(path.read_text(encoding="utf-8")) != data:
            _save(path, data)
        return
    data = json.loads(path.read_text(encoding="utf-8-sig")) if path.exists() else {}
    if not isinstance(data, dict):
        raise ValueError(f"Unexpected JSON structure: {path}")
    before = json.dumps(data, sort_keys=True)
    data.pop(NAME, None)
    if not uninstall:
        entry = {}
        for event in EVENTS[agent]:
            handler = {"type": "command", "command": _cmdline(sys.executable, HOOK, agent, event), "timeout": 3}
            entry[event] = [{"matcher": "*", "hooks": [handler]}] if event.endswith("ToolUse") else [handler]
        data[NAME] = entry
    if json.dumps(data, sort_keys=True) != before:
        _save(path, data)
    cli = home / ".gemini" / "antigravity-cli" / "settings.json"
    if cli.parent.exists():  # the CLI reads statusLine from its own settings file
        settings = json.loads(cli.read_text(encoding="utf-8-sig")) if cli.exists() else {}
        if not isinstance(settings, dict):
            raise ValueError(f"Unexpected JSON structure: {cli}")
        before = json.dumps(settings, sort_keys=True)
        _statusline(settings, uninstall, "Antigravity")
        if json.dumps(settings, sort_keys=True) != before:
            _save(cli, settings)


def install(agent: str, uninstall: bool) -> None:
    if agent in ("copilot", "antigravity"):
        return install_dedicated(agent, uninstall)
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
    command = _cmdline(sys.executable, HOOK, agent)
    # Older releases registered backslash paths; clean those up too.
    suffixes = tuple({" " + _cmdline(HOOK, agent),
                      " " + (subprocess.list2cmdline([str(HOOK), agent]) if os.name == "nt"
                             else shlex.join([str(HOOK), agent]))})
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
                and h["command"].endswith(suffixes)
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
    if agent == "claude":
        _statusline(data, uninstall, "Claude")
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
    parser.add_argument("--agent", choices=["all", *EVENTS], default="all")
    parser.add_argument("--uninstall", action="store_true")
    parser.add_argument("--check-url", metavar="URL", help="validate a server origin with the hook's rules and exit")
    args = parser.parse_args()
    if args.check_url:
        try:
            from bridge import hook
        except ImportError:  # executed as a script: bridge/ is sys.path[0]
            import hook
        try:
            hook.connect(args.check_url).close()
        except ValueError as error:
            parser.error(str(error))
        return
    pin = HERE.parent / ".python-version"  # absent in the standalone bundle, which runs on any recent Python 3
    wanted = pin.read_text().strip() if pin.exists() else None
    if wanted and not args.uninstall and ".".join(map(str, sys.version_info[:3])) != wanted:
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
