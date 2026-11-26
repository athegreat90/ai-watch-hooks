<#
.SYNOPSIS
AI Watch hooks standalone installer for Windows (PowerShell 5.1 and 7). No git clone needed.
.DESCRIPTION
Downloads the checksum-verified release bundle, keeps it in a permanent folder and registers the hooks of your
agent CLIs. The token is read from -TokenFile, the AI_WATCH_TOKEN variable or a hidden prompt, never from the
command line. An existing config.local.json is never overwritten. Needs Python 3.8+.
.EXAMPLE
.\install.ps1 -Url https://your.server
.EXAMPLE
.\install.ps1 -Update
.EXAMPLE
.\install.ps1 -Uninstall -Purge
#>
[CmdletBinding()]
param(
    [string]$Url = $env:AI_WATCH_URL,
    [string]$TokenFile,
    [string]$Version,
    [ValidateSet('', 'claude', 'codex', 'gemini', 'copilot', 'antigravity')][string]$Agent = '',
    [string]$Dir,
    [string]$Repo = $(if ($env:AI_WATCH_HOOKS_REPO) { $env:AI_WATCH_HOOKS_REPO } else { 'athegreat90/ai-watch-hooks' }),
    [switch]$Update,
    [switch]$Uninstall,
    [switch]$Purge,
    [switch]$NoTest
)
$ErrorActionPreference = 'Stop'
try { [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12 } catch { }

function Note([string]$Message) { Write-Host "==> $Message" }
function Fail([string]$Message) { throw "error: $Message" }

if (-not $Dir) {
    $base = if ($env:LOCALAPPDATA) { $env:LOCALAPPDATA } else { Join-Path $HOME '.local/share' }
    $Dir = if ($env:AI_WATCH_HOOKS_DIR) { $env:AI_WATCH_HOOKS_DIR } else { Join-Path $base 'ai-watch-hooks' }
}
$releaseApi = if ($env:AI_WATCH_HOOKS_RELEASE_API) { $env:AI_WATCH_HOOKS_RELEASE_API } else { "https://api.github.com/repos/$Repo" }
$releaseBase = if ($env:AI_WATCH_HOOKS_RELEASE_BASE) { $env:AI_WATCH_HOOKS_RELEASE_BASE } else { "https://github.com/$Repo/releases/download" }
$tagPattern = '^v(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$'
if ($Version -and $Version -ne 'latest' -and $Version -notmatch $tagPattern) { Fail "-Version must be 'latest' or vX.Y.Z" }
if ($Purge -and -not $Uninstall) { Fail '-Purge only makes sense with -Uninstall' }

# Invoke-Python <args>: run the selected interpreter (python.exe or the py launcher) with the arguments.
function Invoke-Python {
    $exe = $script:PythonExe
    $prefix = @($script:PythonPrefix)
    & $exe @prefix @args
}

# Find-Python: the first interpreter that really is Python 3.8+ (this also skips the Windows Store stubs).
function Find-Python {
    $candidates = @()
    if ($env:AI_WATCH_PYTHON) { $candidates += , @($env:AI_WATCH_PYTHON) }
    $candidates += , @('python3'), @('python'), @('py', '-3')
    foreach ($candidate in $candidates) {
        $exe = $candidate[0]
        $prefix = @($candidate | Select-Object -Skip 1)
        if (-not (Get-Command $exe -ErrorAction SilentlyContinue)) { continue }
        $previous = $ErrorActionPreference
        $ErrorActionPreference = 'Continue'
        try {
            & $exe @prefix -c 'import sys; sys.exit(sys.version_info < (3, 8))' 2>$null | Out-Null
            $ok = ($LASTEXITCODE -eq 0)
        } catch { $ok = $false } finally { $ErrorActionPreference = $previous }
        if ($ok) { return @{ Exe = $exe; Prefix = $prefix } }
    }
    Fail 'Python 3.8 or newer is required (set AI_WATCH_PYTHON to pick one).'
}

# Invoke-Checked <args>: run Python and fail on a non-zero exit code.
function Invoke-Checked {
    Invoke-Python @args
    if ($LASTEXITCODE -ne 0) { Fail "python $($args -join ' ') failed with exit code $LASTEXITCODE" }
}

# Get-Download <url> <dest>: download a file (http, https or file URLs).
function Get-Download([string]$From, [string]$To) {
    $client = New-Object System.Net.WebClient
    $client.Headers.Add('User-Agent', 'ai-watch-hooks-installer')
    try { $client.DownloadFile($From, $To) } finally { $client.Dispose() }
}

# Get-Sha256 <file>: lowercase hex SHA-256 of a file.
function Get-Sha256([string]$Path) {
    $algorithm = [System.Security.Cryptography.SHA256]::Create()
    try { return (($algorithm.ComputeHash([System.IO.File]::ReadAllBytes($Path)) | ForEach-Object { $_.ToString('x2') }) -join '') }
    finally { $algorithm.Dispose() }
}

# Get-Verified <tag> <asset> <dest>: download a release asset and check it against the release's SHA256SUMS.
function Get-Verified([string]$Tag, [string]$Asset, [string]$To) {
    $sums = [System.IO.Path]::GetTempFileName()
    try {
        Get-Download "$releaseBase/$Tag/SHA256SUMS" $sums
        Get-Download "$releaseBase/$Tag/$Asset" $To
        $expected = $null
        foreach ($line in Get-Content $sums) {
            $parts = $line -split '\s+', 2
            if ($parts.Count -eq 2 -and $parts[1].TrimStart('*') -eq $Asset) { $expected = $parts[0] }
        }
        if (-not $expected -or (Get-Sha256 $To) -ne $expected.ToLowerInvariant()) {
            Remove-Item $To -Force -ErrorAction SilentlyContinue
            Fail "checksum mismatch for ${Asset}: refusing to use it."
        }
    } finally { Remove-Item $sums -Force -ErrorAction SilentlyContinue }
}

$python = Find-Python
$script:PythonExe = $python.Exe
$script:PythonPrefix = $python.Prefix
$pythonVersion = (Invoke-Python -c 'import sys; print(sys.version.split()[0])' | Select-Object -First 1)
if ($pythonVersion -notlike '3.15.*') { Note "Python $pythonVersion works, but the hooks are only tested on 3.15.x." }

$bridge = Join-Path $Dir 'bridge'
$versionFile = Join-Path $Dir 'VERSION'
$installed = if (Test-Path $versionFile) { (Get-Content $versionFile -Raw).Trim() } else { '' }
$agentArgs = @(); if ($Agent) { $agentArgs = @('--agent', $Agent) }

if ($Uninstall) {
    if (Test-Path (Join-Path $bridge 'install.py')) {
        Note 'Removing the hook registrations'
        Invoke-Checked (Join-Path $bridge 'install.py') '--uninstall' @agentArgs
    } else { Note "No installation found in $Dir; nothing to unregister." }
    if ($Purge) {
        if (Test-Path $Dir) { Remove-Item $Dir -Recurse -Force }
        Note "Deleted $Dir (including config.local.json)."
    } elseif (Test-Path $Dir) {
        Get-ChildItem $Dir -Force | Where-Object { $_.Name -ne 'bridge' } | Remove-Item -Recurse -Force
        if (Test-Path $bridge) {
            Get-ChildItem $bridge -Force | Where-Object { $_.Name -ne 'config.local.json' } | Remove-Item -Recurse -Force
        }
        Note "Kept $(Join-Path $bridge 'config.local.json') (use -Purge to delete it too)."
    }
    return
}

if ($installed -and -not $Update -and -not $Version) {
    Note "AI Watch hooks $installed are already installed in $Dir; use -Update or -Version to change them."
    return
}

if (-not $Version -or $Version -eq 'latest') {
    $json = [System.IO.Path]::GetTempFileName()
    try {
        try { Get-Download "$releaseApi/releases/latest" $json } catch { Fail 'could not query the latest release; pass -Version vX.Y.Z' }
        $Version = (Get-Content $json -Raw | ConvertFrom-Json).tag_name
    } finally { Remove-Item $json -Force -ErrorAction SilentlyContinue }
    if ($Version -notmatch $tagPattern) { Fail 'could not determine the latest release; pass -Version vX.Y.Z' }
}

Note "Installing AI Watch hooks $Version into $Dir"
$zip = [System.IO.Path]::GetTempFileName()
$extract = Join-Path ([System.IO.Path]::GetTempPath()) ('ai-watch-hooks-' + [guid]::NewGuid().ToString('N'))
try {
    Get-Verified $Version "ai-watch-hooks-$Version.zip" $zip
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    [System.IO.Compression.ZipFile]::ExtractToDirectory($zip, $extract)
    $source = Join-Path $extract 'ai-watch-hooks'
    if (-not (Test-Path (Join-Path $source 'bridge\hook.py'))) { Fail 'the bundle does not look like AI Watch hooks' }

    New-Item -ItemType Directory -Force -Path $bridge | Out-Null
    Get-ChildItem $bridge -Force | Where-Object { $_.Name -ne 'config.local.json' } | Remove-Item -Recurse -Force
    Copy-Item (Join-Path $source 'bridge\*') $bridge -Recurse -Force
    Copy-Item (Join-Path $source 'VERSION') $versionFile -Force
} finally {
    Remove-Item $zip -Force -ErrorAction SilentlyContinue
    if (Test-Path $extract) { Remove-Item $extract -Recurse -Force -ErrorAction SilentlyContinue }
}

# The configuration is created once and then left alone.
$config = Join-Path $bridge 'config.local.json'
if (-not (Test-Path $config)) {
    $token = $env:AI_WATCH_TOKEN
    if ($TokenFile) { $token = (Get-Content $TokenFile -Raw).Trim() }
    if (-not $Url) { $Url = Read-Host 'AI Watch server URL (https://host or http://192.168.x.y:8765)' }
    if (-not $token) {
        $secure = Read-Host 'Server token (hidden)' -AsSecureString
        $token = [System.Net.NetworkCredential]::new('', $secure).Password
    }
    if (-not $Url -or -not $token) { Fail 'the URL and the token are both required.' }
    $previous = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    Invoke-Python (Join-Path $bridge 'install.py') '--check-url' $Url 2>$null
    $valid = ($LASTEXITCODE -eq 0)
    $ErrorActionPreference = $previous
    if (-not $valid) { Fail 'the URL is not accepted: use an https origin, or a private IPv4 address over http.' }
    $content = ([ordered]@{ url = $Url; token = $token } | ConvertTo-Json) + "`n"
    [System.IO.File]::WriteAllText($config, $content, (New-Object System.Text.UTF8Encoding($false)))
    Note "Wrote $config"
} else { Note "Keeping the existing $config" }

Note 'Registering the hooks (existing agent settings are backed up first)'
Invoke-Checked (Join-Path $bridge 'install.py') @agentArgs

if (-not $NoTest) {
    Invoke-Python (Join-Path $bridge 'send.py') '--status' 'idle'
    if ($LASTEXITCODE -eq 0) { Note 'The server accepted the test event.' }
    else { Write-Warning "the test event was rejected; check the url and token in $config" }
}
Note "Done: AI Watch hooks $Version. Restart your agent CLIs."
