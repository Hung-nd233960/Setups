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

Project scaffolder (also installs `vsc`): `uv tool install --editable common\tools\new-project`, then `new-project <py|data|report|web> <name>` creates a project (git, README, CLAUDE.md, env) in `D:\Personal Projects\` (override with `--dir` or `NEW_PROJECT_DIR`). `link.ps1` also copies the lint configs into `D:\Personal Projects\` so projects there inherit them.

Monthly check-up: `setups check` from [setups-manager](https://github.com/Hung-nd233960/setups-manager) (install: `git clone https://github.com/Hung-nd233960/setups-manager.git "D:\Personal Projects\setups-manager"`, then `uv tool install --editable "D:\Personal Projects\setups-manager"`) reports disk space, cache sizes, available updates and drift (dead PATH entries, broken links, lint configs out of sync, VS Code, the Claude stub, uncommitted or unpushed repos), each with its fix. It changes nothing; `--quick` skips the slow checks and `--json` is for tools and agents. `pwsh -File windows\maintain.ps1` runs the same check, and with `-Clean` (prune caches) or `-Update` (winget, uv tools, rustup, cargo tools, npm globals) does only that maintenance instead.

## Linux

```bash
git clone https://github.com/Hung-nd233960/Setups.git ~/Setups
~/Setups/linux/link.sh
```

`link.sh` symlinks `common/` (nvim, yazi, helix, starship) and `linux/` (fish, kitty, btop, zellij) into `~/.config/`, and the lint configs into `~`. Existing files are renamed to `*.bak-<timestamp>`, never deleted. The Claude Code format hook (`common/lint/format_hook.py`) is registered in `~/.claude/settings.json` per machine; on Linux point its path at `~/Setups/common/lint/format_hook.py`.

## VS Code

`common/vscode/setup.py` (run by both link scripts) sets up one shared `settings.jsonc` and the profiles below. Each profile gets the base extensions (theme, Claude Code, Remote SSH, git, and the same formatters as the Claude format hook: Ruff, Biome, Prettier, taplo, markdownlint, typos) plus its own:

| Profile | Extra extensions | For |
|---|---|---|
| Default | none | Dotfiles: JSON, TOML, YAML, Markdown |
| Python | Python, Pylance, debugger, Python Environments | Packages, CLIs, scripts |
| Data Science | everything in Python, plus Jupyter, Data Wrangler, Quarto, Rainbow CSV, SQLite viewer | Notebooks and analysis |
| Web | Live Preview | HTML/CSS/JS |
| Docs | LaTeX Workshop (latexmk), Tinymist (Typst), Quarto | Reports and papers |
| Rust | rust-analyzer, CodeLLDB | Rust crates |

All profiles share the Default profile's settings, keybindings and snippets, so there is one settings file. Extensions are listed in `profiles.json`.

**Which profile a project uses** is recorded in the project as `.vscode/profile` (committed, with a matching `.vscode/extensions.json`). `new-project` writes it (default by type: py = Python, data = Data Science, report = Docs, web = Web; override with `--profile`, open with `--open`). For other folders: `vsc --set <profile> [dir]`; `vsc [dir]` opens a folder in its profile and `vsc --list` lists them. Each `setup.py` run with VS Code closed also links every marked project in the projects folder to its profile, so File > Open picks it too.

**SSH.** Extensions in a Remote-SSH window run on the server, and VS Code keeps them per profile there. Two levels:

- *Safe* (any host, nothing to do): `remote.SSH.defaultExtensions` installs only Ruff, Python, Pylance and Jupyter, which bundle their own tools. No Claude Code, so no credentials are left on machines you don't control, and no settings are written on the host.
- *Full* (hosts you control): run `linux/link.sh` there. It installs `remote.jsonc` as the host's remote settings (`setup.py --server`): file-watcher exclusions for datasets and training output, a TensorBoard port label, and a list from which each connecting profile copies its own extensions (Data Science brings Jupyter and Data Wrangler, Docs brings LaTeX Workshop and Tinymist, every profile brings Claude Code and the formatters).

Settings are **copied**, not linked: VS Code writes machine-specific values (SSH hosts, database connections) into `settings.json`, and this repo is public. To keep a change made in the UI, run `setup.py --diff` and copy the part you want into `settings.jsonc`. `setup.py --check` reports drift, `--prune` uninstalls extensions that are not listed, and `--sandbox <dir>` tries everything in a throwaway VS Code folder. Creating profiles and linking projects need VS Code closed (otherwise they are skipped with a note). Settings Sync stays off; this repo replaces it.

## Claude Code instructions

`~/.claude/CLAUDE.md` is a stub generated by the link scripts. It only imports, in layers:

| Layer | File | Public? |
|---|---|---|
| How to work, every machine | `common/claude/rules.md` | yes |
| This machine's paths, envs and tools | `windows/claude-machine.md` or `linux/claude-machine.md` | yes |
| Who I am, studies, projects, preferences | `Setups-private/claude/context.md` | **no**: separate private repo, cloned next to this one |

Edit the layers, never the stub. On my own machines, clone the private repo before running the link script: `git clone https://github.com/Hung-nd233960/Setups-private.git` next to Setups (`$HOME\Setups-private`, `~/Setups-private`). Without it the stub skips that import; clone it later and re-run the link script. (The machine files are not called `claude.md` because Windows would load them as those folders' project instructions.)

## Notes

- VS Code settings files are never overwritten once changed locally: `setup.py` keeps a `*.setups-installed` copy of what it last installed and reports local edits as drift instead (`--diff`, then `--force`).

- `.gitattributes` forces LF line endings so Windows checkouts don't break shell/Lua files.
- `common/nvim/lazy-lock.json` is shared. Update plugins on one machine, then commit, so the others follow.
