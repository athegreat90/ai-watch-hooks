# Changelog

## [Unreleased]

- The daily remediation workflow authenticates the security GitHub App by Client ID (`SECURITY_APP_CLIENT_ID`) instead of the deprecated App ID.

## [1.2.1]

- Refresh the `python:3.15.2-slim-bookworm` base image digest (automatic security remediation). The Python version and the hook code are unchanged.
- Daily remediation keeps a single "Daily container vulnerability findings" issue: the lookup lists open issues instead of using the search API, which found nothing for the GitHub App token and opened a new issue every day. A stubbed test runs in CI.

## [1.2.0]

### Added

- Standalone install without the repository: each release now publishes `ai-watch-hooks-<tag>.zip`, `install.sh`, `install.ps1` and `SHA256SUMS`. The installers verify the bundle checksum, keep the code in a permanent folder (`~/.local/share/ai-watch-hooks` or `%LOCALAPPDATA%i-watch-hooks`), create `config.local.json` once from `--url` and a token file, `AI_WATCH_TOKEN` or a hidden prompt, register the hooks and send a test event.
- Installer flags `--version`, `--update`, `--uninstall`, `--purge`, `--agent`, `--no-test` (PowerShell: `-Version`, `-Update`, `-Uninstall`, `-Purge`, `-Agent`, `-NoTest`).
- `install.py --check-url URL` validates a server origin with the hook's own rules.
- End-to-end installer tests (bash, Windows PowerShell 5.1 and PowerShell 7) and release tooling tests.

### Changed

- `install.py` skips the exact-Python-patch check when `.python-version` is absent, as in the standalone bundle. A clone still enforces it.
- `hook.py` builds its connection in a new `connect()` function; delivery behavior is unchanged.
- The release version now follows the newest `## [X.Y.Z]` heading of this changelog when it is higher than the next patch, so a minor release is declared by editing the changelog.
- Update `actions/create-github-app-token` to 3.4.0 in the daily remediation workflow (replaces Dependabot PR #12).
- README rewritten: standalone install, options, update, uninstall, migration, privacy and security, troubleshooting, layout.

### Fixed

- List each finding once in the daily vulnerability issue.

## [1.1.1]

- Accept an `https` origin in `url` (certificate and host name verified, 2 s timeout). Plain `http` still requires a private IPv4 or loopback.

## [1.1.0]

- Add GitHub Copilot CLI (`~/.copilot/hooks/ai-watch.json`) and Antigravity (`~/.gemini/config/hooks.json`) agents.
- Report 5-hour and weekly usage limits: Claude Code and Antigravity CLI through a `statusLine` command (`bridge/statusline.py`, registered only when no status line is set; Antigravity reports the Gemini 5-hour and weekly quota) and Codex from its latest session log.
- Add the `ErrorOccurred` event and a Python-first install guide for Linux and macOS.
- Fix Windows installs: register hook and status line commands with forward-slash paths, because Claude Code runs hooks through Git Bash, which strips backslashes. Re-running the installer replaces the old entries.
- Documentation: merge the install guides, document the event-to-status mapping, config keys, registration files and troubleshooting; add `docs/MAINTAINING.md`.
- Update Trivy to 0.76.2 and add Zsh equivalents for the PowerShell scripts.

## [1.0.0]

- Initial standalone hooks release.
