# Setups

Setup for my machines aka this is where I put dotfiles. May include descriptions if I have free time

## Layout

| Folder | Contents |
|---|---|
| `common/` | Configs that work the same on every OS: `nvim` (AstroNvim v5), `yazi`, `helix`, `starship`, `lint` |
| `linux/` | Linux only: `fish`, `kitty`, `btop`, `zellij` |
| `windows/` | Windows only: PowerShell profile, Windows Terminal settings, `link.ps1` |

Put a config in `common/` when one copy can serve both systems. Per-OS differences belong in the file itself (`yazi.toml` openers use `for = "windows"`, Neovim can check `vim.fn.has("win32")`) or in `linux/` / `windows/`.

## Windows

```powershell
git clone https://github.com/Hung-nd233960/Setups.git $HOME\Setups
& $HOME\Setups\windows\link.ps1
```

`link.ps1` junctions `common\nvim` to `%LOCALAPPDATA%\nvim` and `common\yazi` to `%APPDATA%\yazi\config`, and points both PowerShell profiles at `windows\powershell\profile.ps1`. Tools the profile expects: starship, zoxide, eza, bat, yazi, nvim (install with `winget` / `cargo binstall`). Neovim on Windows also needs a C compiler for Treesitter (Zig works).

## Linux

```bash
git clone https://github.com/Hung-nd233960/Setups.git ~/Setups
~/Setups/linux/link.sh
```

`link.sh` symlinks `common/` (nvim, yazi, helix, starship) and `linux/` (fish, kitty, btop, zellij) into `~/.config/`, and the lint configs into `~`. Existing files are renamed to `*.bak-<timestamp>`, never deleted. The Claude Code format hook (`common/lint/format_hook.py`) is registered in `~/.claude/settings.json` per machine; on Linux point its path at `~/Setups/common/lint/format_hook.py`.

## Notes

- `.gitattributes` forces LF line endings so Windows checkouts don't break shell/Lua files.
- `common/nvim/lazy-lock.json` is shared. Update plugins on one machine, then commit, so the others follow.
