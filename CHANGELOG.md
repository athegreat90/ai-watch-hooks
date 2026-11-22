# Changelog

## [Unreleased]

## [1.1.2]

- Move the container base image from Debian bookworm to trixie (`python:3.15.2-slim-trixie`) to reduce unfixed OS vulnerabilities; `security/refresh_base.py` follows the variant set in `VARIANT`.
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
