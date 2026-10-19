# Interactive-only setup (skipped for scripts/agents so their output stays plain)
if ([Environment]::UserInteractive -and -not [Console]::IsOutputRedirected -and -not [Console]::IsInputRedirected) {

    # Prompt and smarter cd
    if (Get-Command starship -ErrorAction SilentlyContinue) {
        # Catppuccin Powerline preset, kept in the Setups repo (common/starship)
        $env:STARSHIP_CONFIG = Join-Path (Split-Path -Parent (Split-Path -Parent $PSScriptRoot)) 'common\starship\starship.toml'
        Invoke-Expression (&starship init powershell)
    }
    if (Get-Command zoxide   -ErrorAction SilentlyContinue) {
        Invoke-Expression (& { (zoxide init powershell | Out-String) })
        # fish: alias cd="z"
        Remove-Item Alias:cd -Force -ErrorAction SilentlyContinue
        function cd { z @args }
    }

    # ls / ll -> eza (from the fish config)
    if (Get-Command eza -ErrorAction SilentlyContinue) {
        Remove-Item Alias:ls -Force -ErrorAction SilentlyContinue
        function ls { eza --icons always --no-user @args }
        function ll { eza -a --icons always -l --color-scale-mode gradient --smart-group --git --time-style '+%d-%m-%Y %H:%M' --classify=always --no-user @args }
        function la { eza -la --icons always --git --group-directories-first @args }
    }
    if (Get-Command bat -ErrorAction SilentlyContinue) {
        Remove-Item Alias:cat -Force -ErrorAction SilentlyContinue
        function cat { bat --paging=never @args }
    }

    # vi / vim -> nvim
    if (Get-Command nvim -ErrorAction SilentlyContinue) {
        function vi  { nvim @args }
        function vim { nvim @args }
    }

    # yazi wrapper: cd into the last directory when quitting (from the fish config)
    if (Get-Command yazi -ErrorAction SilentlyContinue) {
        function y {
            $tmp = [System.IO.Path]::GetTempFileName()
            yazi @args --cwd-file="$tmp"
            $cwd = Get-Content -Path $tmp -Encoding UTF8
            if ($cwd -and $cwd -ne $PWD.Path) { Set-Location -LiteralPath ([System.IO.Path]::GetFullPath($cwd)) }
            Remove-Item -Path $tmp -ErrorAction SilentlyContinue
        }
    }
}
