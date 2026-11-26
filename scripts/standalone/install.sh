#!/usr/bin/env bash
# AI Watch hooks standalone installer for Linux, macOS and Git Bash/WSL. No git clone needed: it downloads the
# checksum-verified release bundle, keeps it in a permanent folder and registers the hooks of your agent CLIs.
#
#   install.sh --url https://your.server            install the newest stable release (asks for the token)
#   install.sh --version v1.2.0 --url ...           install a specific release
#   install.sh --update                             fetch the newest release, keep config.local.json
#   install.sh --uninstall [--purge]                remove the registrations (--purge also deletes the folder and config)
#   Options: --token-file FILE  --agent claude|codex|gemini|copilot|antigravity  --dir DIR  --no-test  --repo owner/name
#
# The token is read from --token-file, the AI_WATCH_TOKEN variable or a hidden prompt. It is never taken from the
# command line. An existing config.local.json is never overwritten. Needs Python 3.8+ and curl or wget.
set -euo pipefail

repo=${AI_WATCH_HOOKS_REPO:-athegreat90/ai-watch-hooks}
dir=${AI_WATCH_HOOKS_DIR:-$HOME/.local/share/ai-watch-hooks}
url=${AI_WATCH_URL:-} token_file="" version="" agent="" update=0 uninstall=0 purge=0 test=1

usage() { sed -n '2,12p' "$0" | sed 's/^# \{0,1\}//'; }
die() { echo "error: $*" >&2; exit 1; }
note() { echo "==> $*"; }

while [ $# -gt 0 ]; do
    case $1 in
        --url) url=${2:?--url needs a value}; shift ;;
        --token-file) token_file=${2:?--token-file needs a value}; shift ;;
        --version) version=${2:?--version needs a value}; shift ;;
        --agent) agent=${2:?--agent needs a value}; shift ;;
        --dir) dir=${2:?--dir needs a value}; shift ;;
        --repo) repo=${2:?--repo needs a value}; shift ;;
        --update) update=1 ;;
        --uninstall) uninstall=1 ;;
        --purge) purge=1 ;;
        --no-test) test=0 ;;
        -h | --help) usage; exit 0 ;;
        *) usage >&2; die "unknown option $1" ;;
    esac
    shift
done

release_api=${AI_WATCH_HOOKS_RELEASE_API:-https://api.github.com/repos/$repo}
release_base=${AI_WATCH_HOOKS_RELEASE_BASE:-https://github.com/$repo/releases/download}
tag_re='^v(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$'
[ -z "$version" ] || [ "$version" = latest ] || [[ $version =~ $tag_re ]] || die "--version must be 'latest' or vX.Y.Z"
[ -z "$agent" ] || [[ $agent =~ ^(claude|codex|gemini|copilot|antigravity)$ ]] || die "unknown --agent $agent"
[ "$purge" = 0 ] || [ "$uninstall" = 1 ] || die "--purge only makes sense with --uninstall"

# Pick the first interpreter that really is Python 3.8+ (this also skips the Windows Store stubs).
python=""
for candidate in "${AI_WATCH_PYTHON:-}" python3 python "py -3"; do
    [ -n "$candidate" ] || continue
    # shellcheck disable=SC2086
    if $candidate -c 'import sys; sys.exit(sys.version_info < (3, 8))' >/dev/null 2>&1; then python=$candidate; break; fi
done
[ -n "$python" ] || die "Python 3.8 or newer is required (set AI_WATCH_PYTHON to pick one)."
# shellcheck disable=SC2086
runpy() { $python "$@"; }
pyver=$(runpy -c 'import sys; print("%d.%d.%d" % sys.version_info[:3])')
case $pyver in 3.15.*) ;; *) note "Python $pyver works, but the hooks are only tested on 3.15.x." ;; esac

download() { # url dest
    if command -v curl >/dev/null; then curl -fsSL --retry 3 -o "$2" "$1"
    elif command -v wget >/dev/null; then wget -q -O "$2" "$1"
    else die "curl or wget is required to download release files."; fi
}
sha256() { if command -v sha256sum >/dev/null; then sha256sum "$1" | cut -d' ' -f1; else shasum -a 256 "$1" | cut -d' ' -f1; fi; }

# fetch_verified <tag> <asset> <dest>: download a release asset and check it against the release's SHA256SUMS.
fetch_verified() {
    local tag=$1 asset=$2 dest=$3 sums expected
    sums=$(mktemp)
    download "$release_base/$tag/SHA256SUMS" "$sums" || { rm -f "$sums"; return 1; }
    download "$release_base/$tag/$asset" "$dest" || { rm -f "$sums" "$dest"; return 1; }
    expected=$(awk -v f="$asset" '$2 == f || $2 == "*" f { print $1 }' "$sums")
    rm -f "$sums"
    [ -n "$expected" ] && [ "$(sha256 "$dest")" = "$expected" ] || { rm -f "$dest"; die "checksum mismatch for $asset: refusing to use it."; }
}

bridge=$dir/bridge
installed_version=$(cat "$dir/VERSION" 2>/dev/null || true)

if [ "$uninstall" = 1 ]; then
    if [ -f "$bridge/install.py" ]; then
        note "Removing the hook registrations"
        # shellcheck disable=SC2046
        runpy "$bridge/install.py" --uninstall ${agent:+--agent "$agent"}
    else
        note "No installation found in $dir; nothing to unregister."
    fi
    if [ "$purge" = 1 ]; then rm -rf "$dir"; note "Deleted $dir (including config.local.json)."
    elif [ -d "$dir" ]; then
        find "$dir" -mindepth 1 -maxdepth 1 ! -name bridge -exec rm -rf {} +
        find "$bridge" -mindepth 1 -maxdepth 1 ! -name config.local.json -exec rm -rf {} + 2>/dev/null || true
        note "Kept $bridge/config.local.json (use --purge to delete it too)."
    fi
    exit 0
fi

if [ -n "$installed_version" ] && [ "$update" = 0 ] && [ -z "$version" ]; then
    note "AI Watch hooks $installed_version are already installed in $dir; use --update or --version to change them."
    exit 0
fi

if [ -z "$version" ] || [ "$version" = latest ]; then
    # A temp file instead of /dev/stdout: curl cannot write to /dev/stdout under Git Bash on Windows.
    latest_json=$(mktemp)
    download "$release_api/releases/latest" "$latest_json" || { rm -f "$latest_json"; die "could not query the latest release; pass --version vX.Y.Z"; }
    version=$(sed -n 's/.*"tag_name": *"\([^"]*\)".*/\1/p' "$latest_json" | head -1)
    rm -f "$latest_json"
    [[ $version =~ $tag_re ]] || die "could not determine the latest release; pass --version vX.Y.Z"
fi

note "Installing AI Watch hooks $version into $dir"
zip=$(mktemp)
extract=$(mktemp -d)
trap 'rm -rf "$zip" "$extract"' EXIT
fetch_verified "$version" "ai-watch-hooks-$version.zip" "$zip" || die "could not download the hooks bundle for $version"
if command -v unzip >/dev/null; then unzip -q "$zip" -d "$extract"; else runpy -m zipfile -e "$zip" "$extract"; fi
[ -f "$extract/ai-watch-hooks/bridge/hook.py" ] || die "the bundle does not look like AI Watch hooks"

mkdir -p "$bridge"
find "$bridge" -mindepth 1 -maxdepth 1 ! -name config.local.json -exec rm -rf {} +
cp -R "$extract"/ai-watch-hooks/bridge/. "$bridge/"
cp "$extract/ai-watch-hooks/VERSION" "$dir/VERSION"

# The configuration is created once and then left alone.
config=$bridge/config.local.json
if [ ! -f "$config" ]; then
    token=${AI_WATCH_TOKEN:-}
    if [ -n "$token_file" ]; then token=$(tr -d '\r\n' < "$token_file"); fi
    if [ -z "$url" ] || [ -z "$token" ]; then
        [ -r /dev/tty ] || die "no config yet: pass --url and --token-file (or set AI_WATCH_URL and AI_WATCH_TOKEN)."
        [ -n "$url" ] || { read -r -p "AI Watch server URL (https://host or http://192.168.x.y:8765): " url < /dev/tty; }
        [ -n "$token" ] || { read -r -s -p "Server token (hidden): " token < /dev/tty; echo; }
    fi
    [ -n "$url" ] && [ -n "$token" ] || die "the URL and the token are both required."
    runpy "$bridge/install.py" --check-url "$url" \
        || die "the URL is not accepted: use an https origin, or a private IPv4 address over http."
    (
        umask 077
        # The token travels in the environment of this one process, never on a command line.
        AIW_URL=$url AIW_TOKEN=$token runpy -c 'import json, os, sys
fd = os.open(sys.argv[1], os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
with os.fdopen(fd, "w", encoding="utf-8") as f:
    json.dump({"url": os.environ["AIW_URL"], "token": os.environ["AIW_TOKEN"]}, f, indent=2)
    f.write("\n")' "$config"
    )
    note "Wrote $config"
else
    note "Keeping the existing $config"
fi

note "Registering the hooks (existing agent settings are backed up first)"
# shellcheck disable=SC2046
runpy "$bridge/install.py" ${agent:+--agent "$agent"}

if [ "$test" = 1 ]; then
    if runpy "$bridge/send.py" --status idle; then note "The server accepted the test event."
    else echo "warning: the test event was rejected; check the url and token in $config" >&2; fi
fi
note "Done: AI Watch hooks $version. Restart your agent CLIs."
