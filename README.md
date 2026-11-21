# AI Watch hooks


## Install on the machine running your AI agents

Deploy the [server](https://github.com/athegreat90/ai-watch-server) first. Clone this repository into a permanent directory because hook registrations use absolute paths.

Use the exact stable patch in `.python-version`. Windows x86-64 can install that patch with the Python install manager (for example, `py install 3.15.2`). On Linux x86-64 or ARM64, install the same CPython patch from your package manager or python.org. On macOS ARM64, use the matching official universal2 installer. Check the interpreter with `--version`.

Copy `bridge/config.example.json` to ignored `bridge/config.local.json`. Set `url` to the server origin, such as `http://192.168.1.50:8765`, and set `token` to the server's token.

```powershell
py -3.15 bridge/install.py
py -3.15 bridge/send.py --agent Codex --status working
```

On Linux or macOS use `zsh scripts/install-ai-hooks.zsh` and `python3.15 bridge/send.py --agent Codex --status working` when the pin is in the 3.15 series. Set `AI_WATCH_PYTHON` to select an interpreter for the Zsh script. Restart your agent CLIs. In Codex, review and trust the commands under `/hooks`. Run a short agent task and confirm its status on the watch.

Append `--uninstall` to the installation command to remove your registrations. Use `--agent codex`, `--agent claude`, or `--agent gemini` to select one agent.

## Run a one-shot Docker forwarder

This optional Linux container reads one event from stdin. Substitute an absolute config path and an origin reachable from Docker.

```sh
printf '%s\n' '{"session_id":"example","hook_event_name":"UserPromptSubmit","cwd":"/example"}' |
  docker run --rm -i --mount type=bind,source=/absolute/path/config.local.json,target=/app/config.local.json,readonly \
  ghcr.io/athegreat90/ai-watch-hooks:v1.0.0 codex
```

## Releases

A successful code-changing push to main produces one new patch release. Reruns reuse its version. See [GitHub Releases](https://github.com/athegreat90/ai-watch-hooks/releases).

## Security

CI scans images and Python source. Daily remediation validates pinned Python image updates before opening a PR. Set repository variable SECURITY_APP_ID and secret SECURITY_APP_PRIVATE_KEY using a GitHub App installed on this repository with Contents, Pull requests and Issues write permissions. Require passing checks and human review on main. Review findings without a patch in the daily tracking issue.


Related repositories: [server](https://github.com/athegreat90/ai-watch-server) | [firmware](https://github.com/athegreat90/ai-watch-firmware)
