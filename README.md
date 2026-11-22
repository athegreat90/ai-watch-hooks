# AI Watch hooks

Standard-library Python hooks that report what your AI coding agents are doing (working, needs you, done, error) to the [AI Watch server](https://github.com/athegreat90/ai-watch-server). Nothing is installed except the hook registrations. Prompts and tool arguments are never sent.

```
agent CLI --hook event--> hook.py --POST /api/events--> server --> watch
```

Related repositories: [server](https://github.com/athegreat90/ai-watch-server) | [firmware](https://github.com/athegreat90/ai-watch-firmware). This is hooks v1.1.0; use it with the 1.1.0 server.

## Requirements

- A running server, deployed first, and its URL and token.
- The exact Python patch in `.python-version`. Check with `--version`.
  - Windows x86-64: the Python install manager, for example `py install <version>`.
  - Linux x86-64 or ARM64: your package manager or python.org.
  - macOS ARM64: the official universal2 installer.
- One or more supported agents installed: `claude`, `codex`, `gemini`, `copilot` (GitHub Copilot CLI) or `antigravity`. Agents whose config folder is missing are skipped.

## Quick start

Clone this repository into a permanent directory, because hook registrations use absolute paths.

1. Copy `bridge/config.example.json` to the ignored `bridge/config.local.json`. Set `url` to the server origin, such as `http://192.168.1.50:8765`, and `token` to the server's token.
2. Register the hooks, then send a test event.

   PowerShell (use the interpreter version from `.python-version`):

   ```powershell
   py -3.15 bridge/install.py
   py -3.15 bridge/send.py --agent Codex --status working
   ```

   Linux or macOS:

   ```sh
   python3 bridge/install.py            # or: zsh scripts/install-ai-hooks.zsh
   python3 bridge/send.py --agent "GitHub Copilot CLI" --status working
   ```

   Set `AI_WATCH_PYTHON` to select an interpreter for the Zsh script.
3. Restart your agent CLIs. In Codex, review and trust the commands under `/hooks`.
4. Run a short agent task and confirm its status on the watch.

## Configuration

`bridge/config.local.json` has two keys:

| Key | Meaning |
|---|---|
| `url` | Server origin. It must be a private IPv4 (`10.x`, `172.16-31.x`, `192.168.x`) or loopback over plain `http`, with no path |
| `token` | The server's token (`X-Monitor-Key`) |

## Choose agents and uninstall

Append `--agent codex|claude|gemini|copilot|antigravity` to `install.py` to select one agent, and `--uninstall` to remove your registrations. By default every agent found on the machine is registered. Existing config files are backed up before they change.

Where each agent is registered:

| Agent | File |
|---|---|
| Claude Code | `~/.claude/settings.json` |
| Codex | `$CODEX_HOME/hooks.json` (default `~/.codex/hooks.json`) |
| Gemini CLI | `~/.gemini/settings.json` |
| GitHub Copilot CLI | `~/.copilot/hooks/ai-watch.json` |
| Antigravity | `~/.gemini/config/hooks.json` |

## What is reported

Each agent event becomes one status. Events not listed are ignored.

| Status | Events |
|---|---|
| `working` | `UserPromptSubmit`, `BeforeAgent`, `PreToolUse`, `BeforeTool`, `PostToolUse`, `AfterTool`, `PreInvocation` |
| `needs_attention` | `PermissionRequest`, and `Notification` of type `permission_prompt`, `elicitation_dialog` or `ToolPermission` |
| `done` | `Stop`, `AfterAgent`, `SessionEnd` |
| `idle` | `SessionStart`, `Interrupt` |
| `error` | `PostToolUseFailure`, `StopFailure`, `ErrorOccurred` |

Each event carries the agent name, a hashed session ID, the project folder name, the status and a short fixed description. Antigravity has no permission event, so it reports working and done but never "needs you".

The hook waits at most half a second for the server and exits silently on any error, so an offline server never blocks your agent.

## Usage limits

Codex limits are read from its latest session log after each event. Claude Code and the Antigravity CLI only expose limits to their status line, so `install.py` sets `statusLine` to `bridge/statusline.py` when you have none (Claude: `~/.claude/settings.json`, Antigravity: `~/.gemini/antigravity-cli/settings.json`). It prints `5h 31% | 7d 98%`; for Antigravity this replaces the built-in credits readout and reports the Gemini quota. If you already use a status line, keep it: pipe the same JSON to `python3 bridge/statusline.py > /dev/null` from your script.

## Troubleshooting

- Nothing appears on the watch: run `bridge/send.py` as in the quick start, then check `url` and `token`. HTTP 401 means the token differs from the server's.
- `url` is rejected: use a private IPv4 address over `http`, not a host name or `https`.
- Agent does not report after installing: restart the CLI. In Codex, trust the commands under `/hooks`.
- On Windows, hook commands use forward slashes because Claude Code runs hooks through Git Bash. Re-running the installer replaces old entries.

## Optional: one-shot Docker forwarder

This Linux container reads one event from stdin. Substitute an absolute config path, an origin reachable from Docker and the release tag.

```sh
printf '%s\n' '{"session_id":"example","hook_event_name":"UserPromptSubmit","cwd":"/example"}' |
  docker run --rm -i --mount type=bind,source=/absolute/path/config.local.json,target=/app/config.local.json,readonly \
  ghcr.io/athegreat90/ai-watch-hooks:<tag> codex
```

## Releases and maintenance

See [GitHub Releases](https://github.com/athegreat90/ai-watch-hooks/releases) and the [changelog](CHANGELOG.md). CI, security automation and release rules are in [docs/MAINTAINING.md](docs/MAINTAINING.md).
