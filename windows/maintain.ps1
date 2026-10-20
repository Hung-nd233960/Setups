<#
.SYNOPSIS
  Monthly machine check-up. The checks live in setups-manager (`setups check`); this
  script runs them and adds the two maintenance actions.
.DESCRIPTION
  Default: `setups check`, report only, changes nothing (exit 1 if something needs attention).
  -Clean   prune package caches (uv, conda, npm verify, cargo download cache)
  -Update  winget upgrade --all, uv tools, rustup, cargo-installed tools, npm globals
  With -Clean or -Update only those run; check afterwards with `setups check`.
  Run with PowerShell 7:  pwsh -File C:\Users\DELL\Setups\windows\maintain.ps1 [-Clean] [-Update]
#>
param([switch]$Clean, [switch]$Update)

$ErrorActionPreference = 'Continue'
$env:Path = [Environment]::GetEnvironmentVariable('Path', 'Machine') + ';' + [Environment]::GetEnvironmentVariable('Path', 'User')

if (-not ($Clean -or $Update)) {
    if (-not (Get-Command setups -ErrorAction SilentlyContinue)) {
        "setups-manager is not installed: uv tool install --editable 'D:\Personal Projects\setups-manager'"
        exit 1
    }
    setups check
    exit $LASTEXITCODE
}

if ($Clean) {
    "`n== Cleaning"
    uv cache prune 2>&1 | Select-Object -Last 1
    conda clean --all -y 2>&1 | Select-Object -Last 1
    npm cache verify 2>&1 | Select-Object -Last 1
    $cargoCache = "$HOME\.cargo\registry\cache"
    if (Test-Path $cargoCache) { Remove-Item -Recurse -Force $cargoCache; "  removed cargo download cache (re-downloaded on demand)" }
}

if ($Update) {
    "`n== Updating"
    winget upgrade --all --silent --accept-package-agreements --accept-source-agreements 2>&1 | Select-String 'Successfully|No installed package|failed' | Select-Object -Last 10
    uv tool upgrade --all 2>&1 | Select-Object -Last 3
    rustup update 2>&1 | Select-String 'unchanged|updated' | Select-Object -Last 2
    $crates = cargo install --list 2>$null | Where-Object { $_ -match '^\S+ v' } | ForEach-Object { ($_ -split ' ')[0] }
    if ($crates) { cargo binstall -y --locked @crates 2>&1 | Select-String 'Done|already|error' | Select-Object -Last 3 }
    npm update -g 2>&1 | Select-Object -Last 2
}
