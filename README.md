# AI Watch hooks

Standard-library Python hooks that report what your AI coding agents are doing (working, needs you, done, error) to the [AI Watch server](https://github.com/athegreat90/ai-watch-server). Nothing is installed except the hook registrations. Prompts and tool arguments are never sent.

```
agent CLI --hook event--> hook.py --POST /api/events--> server --> watch
```

Related repositories: [server](https://github.com/athegreat90/ai-watch-server) | [firmware](https://github.com/athegreat90/ai-watch-firmware). This is hooks v1.2.0. It works with the AI Watch server 1.1.x (the Go server and the older Python server share the same `/api/events` and `/api/limits` contract).

## Contents

- [Install without the repository (recommended)](#install-without-the-repository-recommended)
- [Install from source](#install-from-source)
- [Update, uninstall and migrate](#update-uninstall-and-migrate)
- [Configuration](#configuration)
- [Agents and where they are registered](#agents-and-where-they-are-registered)
- [What is reported](#what-is-reported)
- [Privacy and security](#privacy-and-security)
- [Usage limits](#usage-limits)
- [Troubleshooting](#troubleshooting)
- [Optional: one-shot Docker forwarder](#optional-one-shot-docker-forwarder)
- [Releases and maintenance](#releases-and-maintenance)
- [Repository layout and tests](#repository-layout-and-tests)

## Install without the repository (recommended)

You need a running AI Watch server (its URL and token), Python 3.8 or newer, and at least one supported agent CLI: `claude`, `codex`, `gemini`, `copilot` (GitHub Copilot CLI) or `antigravity`. Agents whose config folder is missing are skipped. No `git`, no clone, no build.

The installer downloads the release bundle, **verifies it against the release's `SHA256SUMS`**, keeps it in a permanent folder, writes your configuration once and registers the hooks (your existing agent settings are backed up first). It then sends one test event.

**Linux, macOS, Git Bash, WSL**

```sh
curl -fsSL https://github.com/athegreat90/ai-watch-hooks/releases/latest/download/install.sh | bash -s -- --url https://your.server
```

The token is asked at a hidden prompt. To avoid the prompt, put it in a file and add `--token-file ~/ai-watch.token`, or set `AI_WATCH_TOKEN` for the command. Prefer to read the script first? Download it, inspect it, then run `bash install.sh --url ...`.

**Windows (PowerShell 5.1 or 7)**

```powershell
irm https://github.com/athegreat90/ai-watch-hooks/releases/latest/download/install.ps1 -OutFile install.ps1
.\install.ps1 -Url https://your.server
```

When the execution policy blocks the script, run it with `powershell -ExecutionPolicy Bypass -File .\install.ps1 -Url ...`.

Restart your agent CLIs afterwards. In Codex, review and trust the commands under `/hooks`. Then run a short agent task and confirm its status on the watch.

### Installer options

| Bash | PowerShell | Meaning |
|---|---|---|
| `--url URL` | `-Url URL` | Server origin (asked when missing and no config exists) |
| `--token-file FILE` | `-TokenFile FILE` | File that contains the token. Otherwise `AI_WATCH_TOKEN` or a hidden prompt |
| `--version vX.Y.Z` | `-Version vX.Y.Z` | Install a specific release instead of the newest stable one |
| `--agent NAME` | `-Agent NAME` | Register one agent only: `claude`, `codex`, `gemini`, `copilot`, `antigravity` |
| `--update` | `-Update` | Download the newest release and keep `config.local.json` |
| `--uninstall` | `-Uninstall` | Remove the registrations. The configuration stays |
| `--purge` | `-Purge` | With uninstall, also delete the install folder and the configuration |
| `--no-test` | `-NoTest` | Skip the test event |
| `--dir DIR` | `-Dir DIR` | Install folder |
| `--repo owner/name` | `-Repo owner/name` | Use another GitHub repository (for forks) |

The token is never accepted on the command line, so it does not end up in your shell history or the process list.

| Variable | Meaning |
|---|---|
| `AI_WATCH_URL`, `AI_WATCH_TOKEN` | Same as `--url` and the token source |
| `AI_WATCH_HOOKS_DIR` | Install folder |
| `AI_WATCH_HOOKS_REPO` | GitHub repository to download from |
| `AI_WATCH_PYTHON` | Interpreter to use (default: the first working `python3`, `python` or `py -3`) |

### Where everything lives

| Item | Linux, macOS, Git Bash | Windows PowerShell |
|---|---|---|
| Install folder | `~/.local/share/ai-watch-hooks` | `%LOCALAPPDATA%\ai-watch-hooks` |
| Code | `<folder>/bridge/*.py` | `<folder>\bridge\*.py` |
| Configuration | `<folder>/bridge/config.local.json` | `<folder>\bridge\config.local.json` |
| Installed version | `<folder>/VERSION` | `<folder>\VERSION` |

The folder is fixed, so updates replace the code in place and never touch the configuration. Hook registrations point at the files in this folder; do not move it. If you move it anyway, run the installer again.

## Install from source

Use this when you work on the hooks themselves. Clone this repository into a permanent directory, because hook registrations use absolute paths.

1. Copy `bridge/config.example.json` to the ignored `bridge/config.local.json`. Set `url` to the server origin and `token` to the server's token.
2. Use the exact Python patch in `.python-version` (check with `--version`). On Windows x86-64 use the Python install manager, for example `py install <version>`; on Linux x86-64 or ARM64 use your package manager or python.org; on macOS ARM64 use the official universal2 installer.
3. Register the hooks, then send a test event.

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
4. Restart your agent CLIs. In Codex, review and trust the commands under `/hooks`.

## Update, uninstall and migrate

- **Update**: `install.sh --update` or `install.ps1 -Update` (the one-line commands above work too, with `--update`). A normal run on an installed machine does nothing and tells you the installed version.
- **Pin a release or go back**: pass `--version vX.Y.Z` (`-Version vX.Y.Z`). Older releases stay available on the Releases page.
- **Uninstall**: `install.sh --uninstall` (`-Uninstall`). Add `--purge` (`-Purge`) to delete the folder and the token as well. Backups of agent settings (`*.backup-<timestamp>`) are left where they are.
- **Migrate from a clone**: run `python <clone>/bridge/install.py --uninstall` once, then install with the standalone installer. The installer removes only entries that end with its own `hook.py` path, so skipping the first step leaves the old entries in place and every event is sent twice. Your old `bridge/config.local.json` can be reused: pass the same URL and a token file.

## Configuration

`config.local.json` has two keys:

| Key | Meaning |
|---|---|
| `url` | Server origin. Either an `https` origin with a host name (the certificate is verified), or a private IPv4 (`10.x`, `172.16-31.x`, `192.168.x`) or loopback over plain `http`. No path or user name |
| `token` | The server's token (`X-Monitor-Key`) |

The bash installer creates the file with mode `0600`; on Windows it lives in your user profile folder. Both installers validate the URL with the same rules the hook uses (`install.py --check-url URL`).

## Agents and where they are registered

By default every agent found on the machine is registered. Existing config files are backed up before they change.

| Agent | File |
|---|---|
| Claude Code | `~/.claude/settings.json` |
| Codex | `$CODEX_HOME/hooks.json` (default `~/.codex/hooks.json`) |
| Gemini CLI | `~/.gemini/settings.json` |
| GitHub Copilot CLI | `~/.copilot/hooks/ai-watch.json` |
| Antigravity | `~/.gemini/config/hooks.json` |

Claude Code, Codex and Gemini CLI are registered only when their CLI is on `PATH`. Copilot CLI and Antigravity are registered when their config folder exists. Antigravity has no permission event, so it reports working and done but never "needs you".

## What is reported

Each agent event becomes one status. Events not listed are ignored.

| Status | Events |
|---|---|
| `working` | `UserPromptSubmit`, `BeforeAgent`, `PreToolUse`, `BeforeTool`, `PostToolUse`, `AfterTool`, `PreInvocation` |
| `needs_attention` | `PermissionRequest`, and `Notification` of type `permission_prompt`, `elicitation_dialog` or `ToolPermission` |
| `done` | `Stop`, `AfterAgent`, `SessionEnd` |
| `idle` | `SessionStart`, `Interrupt` |
| `error` | `PostToolUseFailure`, `StopFailure`, `ErrorOccurred` |

## Privacy and security

Each event carries only: the agent name, the SHA-256 hash of the session ID, the project folder name (last path segment, at most 40 characters), the status, a short fixed description and a timestamp. Prompts, tool names, tool arguments, tool output and full paths are never sent. Usage limits carry only percentages and reset times.

- **Transport**: an `https` origin is verified (certificate and host name, 2 s timeout). Plain `http` is accepted only for private IPv4 addresses and loopback (0.5 s timeout).
- **Failure mode**: the hook exits silently on any error, so an offline server never blocks or slows your agent. The timeouts registered with each agent are a few seconds.
- **Token**: stored only in `config.local.json`; the installer never takes it from the command line.
- **Downloads**: the installer refuses any bundle whose SHA-256 differs from the release's `SHA256SUMS`. The one-line command trusts GitHub and the release in the same way; download and read `install.sh` first if you want to review it.
- **Backups**: every agent settings file is copied to `<name>.backup-<timestamp>` before it changes. Foreign hooks and settings are preserved.
- **Verify a download by hand**: `sha256sum -c SHA256SUMS --ignore-missing` (Linux), `shasum -a 256 -c SHA256SUMS --ignore-missing` (macOS) in the folder with the downloaded files.

## Usage limits

Codex limits are read from its latest session log after each event. Claude Code and the Antigravity CLI only expose limits to their status line, so the installer sets `statusLine` to `bridge/statusline.py` when you have none (Claude: `~/.claude/settings.json`, Antigravity: `~/.gemini/antigravity-cli/settings.json`). It prints `5h 31% | 7d 98%`; for Antigravity this replaces the built-in credits readout and reports the Gemini quota. If you already use a status line, keep it: pipe the same JSON to `python3 <folder>/bridge/statusline.py > /dev/null` from your script.

## Troubleshooting

| Symptom | What to check |
|---|---|
| Nothing appears on the watch | Run `python <folder>/bridge/send.py --status idle` and check `url` and `token`. HTTP 401 means the token differs from the server's |
| `url` is rejected | Use an `https` origin, or a private IPv4 address over `http`. A host name over plain `http` is not accepted |
| Agent does not report after installing | Restart the CLI. In Codex, trust the commands under `/hooks` |
| Events arrive twice | An old clone registration is still present. Run `python <clone>/bridge/install.py --uninstall` |
| `checksum mismatch` | The download is incomplete or altered. Retry; if it persists, do not use it and report it |
| `Python 3.8 or newer is required` | Install Python, or set `AI_WATCH_PYTHON` to an interpreter. On Windows the Microsoft Store "python" shortcut is not a real interpreter |
| `Install and invoke Python X before registering hooks` | You are running from a clone: use the interpreter named in `.python-version`, or use the standalone installer |
| On Windows, hook commands use forward slashes | Expected: Claude Code runs hooks through Git Bash. Re-running the installer replaces old entries |

## Optional: one-shot Docker forwarder

This Linux container reads one event from stdin. Substitute an absolute config path, an origin reachable from Docker and the release tag.

```sh
printf '%s\n' '{"session_id":"example","hook_event_name":"UserPromptSubmit","cwd":"/example"}' |
  docker run --rm -i --mount type=bind,source=/absolute/path/config.local.json,target=/app/config.local.json,readonly \
  ghcr.io/athegreat90/ai-watch-hooks:<tag> codex
```

## Releases and maintenance

Every release publishes `ai-watch-hooks-<tag>.zip`, `install.sh`, `install.ps1` and `SHA256SUMS` on [GitHub Releases](https://github.com/athegreat90/ai-watch-hooks/releases), plus the Docker image. See the [changelog](CHANGELOG.md). CI, security automation and release rules are in [docs/MAINTAINING.md](docs/MAINTAINING.md).

## Repository layout and tests

| Path | Purpose |
|---|---|
| `bridge/hook.py` | The hook: maps agent events to statuses and posts them |
| `bridge/install.py` | Registers and removes the hooks of each agent (`--agent`, `--uninstall`, `--check-url`) |
| `bridge/limits.py`, `bridge/statusline.py` | Usage limits reporting |
| `bridge/send.py` | Sends one explicit test event |
| `scripts/standalone/` | The standalone installers (`install.sh`, `install.ps1`) shipped with each release |
| `scripts/install-ai-hooks.*` | Convenience wrappers for the source install |
| `release/` | Version selection, release assets (`assets.sh`) and image publishing |
| `tests/` | Unit tests and installer end-to-end tests |

```sh
python -m unittest discover -s tests -v
```

The installer tests build the release assets locally and run both installers (bash, and PowerShell when available) against them in an isolated home folder, with a local receiver instead of a real server.
