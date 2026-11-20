#!/usr/bin/env bash
set -euo pipefail
image=$1
arch=$2
docker run --rm --platform "linux/$arch" --entrypoint python "$image" --version
result=$(printf '%s' '{}' | docker run --rm -i --platform "linux/$arch" "$image" gemini)
test "$result" = '{}'
