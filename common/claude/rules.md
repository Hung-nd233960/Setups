# Working rules (every machine)

Imported by `~/.claude/CLAUDE.md`, which `link.ps1` / `link.sh` generate. Machine facts are in the OS file imported next to this one, personal context in Setups-private.

- **Python packages:** never `pip install` into conda base or any global Python. Use the machine's pre-built envs or a project's own uv env. Missing package: for one-off use, `uv run --project <env> --with <pkg> ...`; if it's broadly useful, `uv add --project <env> <pkg>` and commit in the env repo.
- **Formatting:** a PostToolUse hook formats and lints every file you edit (ruff, Biome, Prettier, taplo; Markdown is lint-only). Fix the issues it reports, and re-read a file before editing a region it may have reformatted.
- **Secrets:** API keys live in user environment variables or a project `.env` (globally git-ignored; commit a `.env.example` with empty values). Never print, log, commit or paste secrets into files, and do not read `.env` files unless the user asks.
- **Citations:** cite only keys that exist in the user's Zotero export (path in the machine file); never invent references.
- **New projects:** create them with `new-project <py|data|report|web> <name>`. It sets up git, README, a project CLAUDE.md, the env and the VS Code profile.
- **These instructions** come from the Setups repos: edit `Setups/common/claude/rules.md`, the OS file or `Setups-private/claude/context.md`, never the generated `~/.claude/CLAUDE.md`. Setups is public: personal details go only in Setups-private.
