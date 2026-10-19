<#
.SYNOPSIS
  Monthly machine check-up: disk, caches, updates, and drift in the AI-ready setup.
.DESCRIPTION
  Default: report only, changes nothing.
  -Clean   prune package caches (uv, conda, npm verify, cargo download cache)
  -Update  winget upgrade --all, uv tools, rustup, cargo-installed tools, npm globals
  Run with PowerShell 7:  pwsh -File C:\Users\DELL\Setups\windows\maintain.ps1 [-Clean] [-Update]
#>
param([switch]$Clean, [switch]$Update)

$ErrorActionPreference = 'Continue'
$env:Path = [Environment]::GetEnvironmentVariable('Path', 'Machine') + ';' + [Environment]::GetEnvironmentVariable('Path', 'User')
$repo = Split-Path -Parent $PSScriptRoot
$warnings = [System.Collections.Generic.List[string]]::new()

function Section($title) { "`n== $title" }
function Ok($msg) { "  ok    $msg" }
function Warn($msg) { "  WARN  $msg"; $warnings.Add($msg) }
function SizeMB($path) {
    if (-not (Test-Path $path)) { return 0 }
    [math]::Round((Get-ChildItem $path -Recurse -Force -File -ErrorAction SilentlyContinue | Measure-Object Length -Sum).Sum / 1MB)
}

Section 'Disk'
foreach ($d in Get-PSDrive -PSProvider FileSystem | Where-Object { $_.Used -ne $null -and $_.Name -in 'C', 'D' }) {
    $freeGB = [math]::Round($d.Free / 1GB, 1); $pct = [math]::Round($d.Free / ($d.Used + $d.Free) * 100)
    if ($pct -lt 15) { Warn "$($d.Name): only $freeGB GB free ($pct %)" } else { Ok "$($d.Name): $freeGB GB free ($pct %)" }
}

Section 'Caches (MB)'
$caches = [ordered]@{
    'uv cache'            = (uv cache dir 2>$null)
    'conda pkgs'          = "$HOME\miniforge3\pkgs"
    'cargo registry'      = "$HOME\.cargo\registry"
    'npm cache'           = (npm config get cache 2>$null)
    'Playwright browsers' = "$env:LOCALAPPDATA\ms-playwright"
    'Temp'                = $env:TEMP
}
foreach ($k in $caches.Keys) {
    $mb = SizeMB $caches[$k]
    $line = '{0,-20} {1,7}' -f $k, $mb
    if ($k -eq 'Temp' -and $mb -gt 5120) { Warn "$line  (large; close apps, then Disk Cleanup or delete old files in %TEMP%)" } elseif ($mb -gt 2048 -and $k -ne 'Temp') { Warn "$line  (large; run with -Clean)" } else { Ok $line }
}

Section 'Setup drift'
$dead = [Environment]::GetEnvironmentVariable('Path', 'User').Split(';') | Where-Object { $_ -and -not (Test-Path $_) }
if ($dead) { Warn "user PATH has missing folders: $($dead -join '; ')" } else { Ok 'user PATH: no dead entries' }

foreach ($j in @{ "$env:LOCALAPPDATA\nvim" = "$repo\common\nvim"; "$env:APPDATA\yazi\config" = "$repo\common\yazi" }.GetEnumerator()) {
    $item = Get-Item $j.Key -Force -ErrorAction SilentlyContinue
    if ($item -and $item.LinkType -eq 'Junction' -and ($item.Target -contains $j.Value)) { Ok "junction $($j.Key)" } else { Warn "junction $($j.Key) is missing or wrong (run link.ps1)" }
}

$lintFiles = '.editorconfig', 'ruff.toml', 'biome.json', '.prettierrc.json', '.yamllint.yaml', '.taplo.toml', '.markdownlint-cli2.jsonc', 'typos.toml'
$stale = $lintFiles | Where-Object { -not (Test-Path "$HOME\$_") -or [IO.File]::ReadAllText("$repo\common\lint\$_") -ne [IO.File]::ReadAllText("$HOME\$_") }
if ($stale) { Warn "home lint configs out of sync with Setups: $($stale -join ', ') (run link.ps1)" } else { Ok 'home lint configs match Setups' }

$vscode = uv run --no-project python "$repo\common\vscode\setup.py" --check 2>&1
if ($LASTEXITCODE) { Warn 'VS Code differs from Setups (common\vscode\setup.py --diff / --prune)'; $vscode | Where-Object { $_ -notmatch '^ok' } | ForEach-Object { "          $_" } } else { Ok 'VS Code settings and extensions match Setups' }

$settings = "$HOME\.claude\settings.json"
if ((Test-Path $settings) -and (Get-Content $settings -Raw) -match 'format_hook\.py') { Ok 'Claude format hook registered' } else { Warn 'Claude format hook not found in settings.json' }

$condaEnvs = (conda env list 2>$null | Where-Object { $_ -and $_ -notmatch '^#' }).Count
if ($condaEnvs -gt 1) { Warn "conda has $condaEnvs envs (expected only base); review with 'conda env list'" } else { Ok 'conda: base only' }
$basePip = (conda list -n base 2>$null | Select-String '\spypi\s*$').Count  # channel column; conda-pypi itself is conda tooling
if ($basePip) { Warn "conda base has $basePip pip-installed packages (base should stay clean)" } else { Ok 'conda base: no pip packages' }

foreach ($e in 'docs', 'ds') {
    $v = (uv run --project "$HOME\envs\$e" python --version 2>$null) -replace 'Python ', ''
    if ($v -like '3.13*') { Ok "envs\$e on Python $v" } else { Warn "envs\$e runs Python '$v' (expected 3.13)" }
}

Section 'Repositories'
foreach ($r in "$HOME\envs", $repo, "$HOME\Documents\CLI-guides") {
    if (-not (Test-Path "$r\.git")) { Warn "$r is not a git repo"; continue }
    $dirty = (git -C $r status --porcelain 2>$null | Measure-Object).Count
    $ahead = if (git -C $r rev-parse --abbrev-ref '@{u}' 2>$null) { (git -C $r rev-list --count '@{u}..HEAD' 2>$null) } else { 'no remote' }
    $msg = '{0,-40} uncommitted: {1}  unpushed: {2}' -f $r, $dirty, $ahead
    if ($dirty -gt 0 -or ($ahead -match '^\d+$' -and [int]$ahead -gt 0)) { Warn $msg } else { Ok $msg }
}

Section 'Updates available'
$wingetUpgrades = winget upgrade --accept-source-agreements 2>$null | Select-String -Pattern '^\S.*\s\d[\d.]+\s+\d[\d.]+\s+winget\s*$'
if ($wingetUpgrades) { Warn "$($wingetUpgrades.Count) winget upgrades (run with -Update or 'winget upgrade')"; $wingetUpgrades | ForEach-Object { "          $($_.Line.Trim())" } } else { Ok 'winget: up to date' }
$rust = rustup check 2>$null | Select-String 'Update available'
if ($rust) { Warn "rustup: $($rust.Line.Trim())" } else { Ok 'rustup: up to date' }

if ($Clean) {
    Section 'Cleaning'
    uv cache prune 2>&1 | Select-Object -Last 1
    conda clean --all -y 2>&1 | Select-Object -Last 1
    npm cache verify 2>&1 | Select-Object -Last 1
    $cargoCache = "$HOME\.cargo\registry\cache"
    if (Test-Path $cargoCache) { Remove-Item -Recurse -Force $cargoCache; "  removed cargo download cache (re-downloaded on demand)" }
}

if ($Update) {
    Section 'Updating'
    winget upgrade --all --silent --accept-package-agreements --accept-source-agreements 2>&1 | Select-String 'Successfully|No installed package|failed' | Select-Object -Last 10
    uv tool upgrade --all 2>&1 | Select-Object -Last 3
    rustup update 2>&1 | Select-String 'unchanged|updated' | Select-Object -Last 2
    $crates = cargo install --list 2>$null | Where-Object { $_ -match '^\S+ v' } | ForEach-Object { ($_ -split ' ')[0] }
    if ($crates) { cargo binstall -y --locked @crates 2>&1 | Select-String 'Done|already|error' | Select-Object -Last 3 }
    npm update -g 2>&1 | Select-Object -Last 2
}

Section 'Summary'
if ($warnings.Count) { "  $($warnings.Count) item(s) need attention:"; $warnings | ForEach-Object { "   - $_" } } else { '  all good' }
