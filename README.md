# AI Watch hooks

Use the exact stable Python release in .python-version. On Windows install it with the Python install manager (`py install 3.15.2`) and invoke `py -3.15 bridge/install.py`. On Linux x86-64 and ARM64 install CPython 3.15.2 from your trusted package manager or python.org source and invoke `python3.15 bridge/install.py`. On macOS ARM64 use the official universal2 installer and invoke `python3.15 bridge/install.py`. Confirm the patch with `--version`. Reuse the same interpreter and append `--uninstall` to remove the hooks.

Copy bridge/config.example.json to bridge/config.local.json and enter the server private LAN origin and matching token. Install from a permanent path. Restart agent CLIs and review new commands in Codex /hooks. Verify with `python bridge/send.py --agent Codex --status working` using the selected interpreter.

The optional Linux container forwards one event through stdin. Use an absolute path for the read-only mount and a host LAN address reachable from the container.

```sh
docker run --rm -i --mount type=bind,source=/absolute/path/config.local.json,target=/app/config.local.json,readonly ghcr.io/<owner>/ai-watch-hooks:v1.0.0 codex < event.json
```

## Security

CI scans images and Python source. Daily remediation validates pinned Python image updates before opening a PR. Set repository variable SECURITY_APP_ID and secret SECURITY_APP_PRIVATE_KEY using a GitHub App installed on this repository with Contents, Pull requests and Issues write permissions. Require passing checks and human review on main. Review findings without a patch in the daily tracking issue.

Related repositories: [server](https://github.com/athegreat90/ai-watch-server) [firmware](https://github.com/athegreat90/ai-watch-firmware)

## Zsh on Linux and macOS

Run `zsh scripts/install-ai-hooks.zsh` to register hooks or
`zsh scripts/install-ai-hooks.zsh --uninstall` to remove them.
Pass `--agent codex`, `--agent claude`, or `--agent gemini` to target one CLI.
The script prefers `python3.15`; set `AI_WATCH_PYTHON` to select a different path.
The installer checks the exact version in `.python-version` before registration.
