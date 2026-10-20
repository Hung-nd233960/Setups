# This machine (Linux)

- Setups is cloned at `~/Setups`; the lint configs are symlinked into `~` and the format hook is `~/Setups/common/lint/format_hook.py` (register it in `~/.claude/settings.json` on each machine).
- `new-project` defaults to `~/Projects/<name>/` (override with `--dir` or `NEW_PROJECT_DIR`).
- This file has no per-machine details yet (envs, GPU, schedulers). Check what is installed before assuming a tool exists, and add what you learn here.
