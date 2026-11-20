#!/usr/bin/env zsh
emulate -L zsh
setopt errexit nounset pipefail
source "${0:A:h}/common.zsh"

"$python_command" "$repo_root/bridge/install.py" "$@"
