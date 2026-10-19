# Link this repo's Windows configs into place. Safe to re-run.
#   nvim  -> %LOCALAPPDATA%\nvim              (junction)
#   yazi  -> %APPDATA%\yazi\config             (junction)
#   shell -> both PowerShell profiles          (one-line stubs that load windows\powershell\profile.ps1)
# Existing non-link targets are renamed to <name>.bak-<timestamp>, never deleted.
$repo = Split-Path -Parent $PSScriptRoot
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'

function Link-Dir($link, $target) {
    if (Test-Path $link) {
        $item = Get-Item $link -Force
        if ($item.LinkType -eq 'Junction' -and $item.Target -contains $target) { "ok       $link"; return }
        if ($item.LinkType -eq 'Junction') { cmd /c rmdir "`"$link`"" }
        else { Rename-Item $link "$($item.Name).bak-$stamp"; "backed up existing $link" }
    }
    New-Item -ItemType Directory -Force (Split-Path $link) | Out-Null
    New-Item -ItemType Junction -Path $link -Target $target | Out-Null
    "linked   $link -> $target"
}

Link-Dir "$env:LOCALAPPDATA\nvim"      "$repo\common\nvim"
Link-Dir "$env:APPDATA\yazi\config"    "$repo\common\yazi"

$stub = ". '$repo\windows\powershell\profile.ps1'"
foreach ($p in "$HOME\Documents\PowerShell\Microsoft.PowerShell_profile.ps1",
               "$HOME\Documents\WindowsPowerShell\Microsoft.PowerShell_profile.ps1") {
    if ((Test-Path $p) -and ((Get-Content $p -Raw).Trim() -eq $stub)) { "ok       $p"; continue }
    if (Test-Path $p) { Copy-Item $p "$p.bak-$stamp" }
    New-Item -ItemType Directory -Force (Split-Path $p) | Out-Null
    Set-Content $p $stub -Encoding utf8
    "profile  $p"
}
"Windows Terminal settings are not linked (Terminal rewrites the file). Copy windows\terminal\settings.json by hand if needed."
