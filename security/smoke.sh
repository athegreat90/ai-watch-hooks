#!/usr/bin/env bash
set -euo pipefail
python3 security/smoke_hook.py "$1" "$2"
