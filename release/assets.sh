#!/usr/bin/env bash
# Build the versioned release assets into dist/: the standalone hooks bundle, the two installers and SHA256SUMS.
# Usage: RELEASE_TAG=v1.2.0 bash release/assets.sh   (needs zip or Python 3, and sha256sum or shasum)
set -euo pipefail
tag=${RELEASE_TAG:?RELEASE_TAG is required}
root=$(cd "$(dirname "$0")/.." && pwd)
dist=${ASSETS_DIR:-$root/dist}
rm -rf "$dist" && mkdir -p "$dist"

# The bundle is flat and self-contained: hook.py and its siblings find each other and config.local.json by directory.
bundle=$(mktemp -d)
trap 'rm -rf "$bundle"' EXIT
mkdir -p "$bundle/ai-watch-hooks/bridge"
for file in hook limits statusline send install; do cp "$root/bridge/$file.py" "$bundle/ai-watch-hooks/bridge/"; done
cp "$root/bridge/config.example.json" "$bundle/ai-watch-hooks/bridge/"
cp "$root/scripts/standalone/install.sh" "$root/scripts/standalone/install.ps1" "$bundle/ai-watch-hooks/"
echo "$tag" > "$bundle/ai-watch-hooks/VERSION"

# Reproducible archive: fixed timestamps and a stable member order.
find "$bundle" -exec touch -t 200001010000 {} +
archive=$dist/ai-watch-hooks-$tag.zip
if command -v zip >/dev/null 2>&1; then
    (cd "$bundle" && find ai-watch-hooks -type f | LC_ALL=C sort | zip -qX "$archive" -@)
else
    python=""
    for candidate in python3 python; do # run it: on Windows python3 can be a Store stub
        if "$candidate" -c 'import zipfile' >/dev/null 2>&1; then python=$candidate; break; fi
    done
    [ -n "$python" ] || { echo "zip or python is required" >&2; exit 1; }
    (cd "$bundle" && "$python" -m zipfile -c "$archive" ai-watch-hooks)
fi

# The installers are also published on their own so one curl/irm line can fetch them.
cp "$root/scripts/standalone/install.sh" "$root/scripts/standalone/install.ps1" "$dist/"

if command -v sha256sum >/dev/null 2>&1; then sum=(sha256sum); else sum=(shasum -a 256); fi
(cd "$dist" && "${sum[@]}" -- ai-watch-hooks-"$tag".zip install.ps1 install.sh > SHA256SUMS)
ls -l "$dist"
