# Setups

Setup for my machines aka this is where I put dotfiles. May include descriptions if I have free time

## Layout

| Folder | Contents |
|---|---|
| `common/` | Configs that work the same on every OS: `nvim` (AstroNvim v5), `yazi`, `helix`, `starship`, `lint`, `vscode` |
| `linux/` | Linux only: `fish`, `kitty`, `btop`, `zellij` |
| `windows/` | Windows only: PowerShell profile, Windows Terminal settings, `link.ps1` |

Put a config in `common/` when one copy can serve both systems. Per-OS differences belong in the file itself (`yazi.toml` openers use `for = "windows"`, Neovim can check `vim.fn.has("win32")`) or in `linux/` / `windows/`.

## Windows

```powershell
git clone https://github.com/Hung-nd233960/Setups.git $HOME\Setups
& $HOME\Setups\windows\link.ps1
```

`link.ps1` junctions `common\nvim` to `%LOCALAPPDATA%\nvim` and `common\yazi` to `%APPDATA%\yazi\config`, and points both PowerShell profiles at `windows\powershell\profile.ps1`. Tools the profile expects: starship, zoxide, eza, bat, yazi, nvim (install with `winget` / `cargo binstall`). Neovim on Windows also needs a C compiler for Treesitter (Zig works).

Project scaffolder: `uv tool install --editable common\tools\new-project`, then `new-project <py|data|report|web> <name>` creates a project (git, README, CLAUDE.md, env) in `D:\Personal Projects\` (override with `--dir` or `NEW_PROJECT_DIR`). `link.ps1` also copies the lint configs into `D:\Personal Projects\` so projects there inherit them.

Monthly check-up: `pwsh -File windows\maintain.ps1` reports disk space, cache sizes, available updates and drift (dead PATH entries, broken junctions, lint configs out of sync, uncommitted repos). It changes nothing unless run with `-Clean` (prune caches) or `-Update` (winget, uv tools, rustup, cargo tools, npm globals).

## Linux

```bash
git clone https://github.com/Hung-nd233960/Setups.git ~/Setups
~/Setups/linux/link.sh
```

`link.sh` symlinks `common/` (nvim, yazi, helix, starship) and `linux/` (fish, kitty, btop, zellij) into `~/.config/`, and the lint configs into `~`. Existing files are renamed to `*.bak-<timestamp>`, never deleted. The Claude Code format hook (`common/lint/format_hook.py`) is registered in `~/.claude/settings.json` per machine; on Linux point its path at `~/Setups/common/lint/format_hook.py`.

## VS Code

`common/vscode/setup.py` (run by both link scripts) sets up one shared `settings.jsonc` and four profiles. Each profile gets the base extensions (theme, Claude Code, Remote SSH, git, and the same formatters as the Claude format hook: Ruff, Biome, Prettier, taplo, markdownlint, typos) plus its own:

| Profile | Extra extensions | For |
|---|---|---|
| Default | none | Dotfiles: JSON, TOML, YAML, Markdown |
| Data Science | Python, Pylance, Jupyter, Data Wrangler, Quarto, Rainbow CSV, SQLite viewer | Notebooks and analysis |
| Web | Live Preview | HTML/CSS/JS |
| Docs | LaTeX Workshop (latexmk), Tinymist (Typst), Quarto | Reports and papers |

All profiles share the Default profile's settings, keybindings and snippets, so there is one settings file. Extensions are listed in `profiles.json`. Open a folder in a profile with `code --profile "Data Science" <folder>`; VS Code remembers the choice for that folder.

Settings are **copied**, not linked: VS Code writes machine-specific values (SSH hosts, database connections) into `settings.json`, and this repo is public. To keep a change made in the UI, run `setup.py --diff` and copy the part you want into `settings.jsonc`. `setup.py --check` reports drift, `--prune` uninstalls extensions that are not listed, and `--sandbox <dir>` tries everything in a throwaway VS Code folder. Creating profiles needs VS Code closed. Settings Sync stays off; this repo replaces it.

## Notes

- `.gitattributes` forces LF line endings so Windows checkouts don't break shell/Lua files.
- `common/nvim/lazy-lock.json` is shared. Update plugins on one machine, then commit, so the others follow.
