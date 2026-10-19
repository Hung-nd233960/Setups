"""Claude Code PostToolUse hook: format and lint the file an agent just edited.

Formatting is applied silently. Remaining lint problems are printed to stderr with
exit code 2, which Claude Code feeds back to the agent (the edit itself stands).
Markdown is linted only, never reformatted (Pandoc/Quarto syntax is fragile).

A project's own config (found by walking up from the file) wins; otherwise the
defaults next to this script are used. Set CLAUDE_FORMAT_HOOK=0 to disable.
"""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

LINT_DIR = Path(__file__).resolve().parent
SKIP_DIRS = {
    "node_modules",
    ".venv",
    "venv",
    ".git",
    "site-packages",
    "__pycache__",
    ".quarto",
}
SKIP_NAMES = {
    "package-lock.json",
    "pnpm-lock.yaml",
    "yarn.lock",
    "uv.lock",
    "Cargo.lock",
    "poetry.lock",
}
TIMEOUT = 30
MAX_LINES = 40

PY = {".py", ".pyi"}
BIOME = {
    ".js",
    ".mjs",
    ".cjs",
    ".jsx",
    ".ts",
    ".mts",
    ".cts",
    ".tsx",
    ".json",
    ".jsonc",
    ".css",
}
PRETTIER = {".html", ".htm", ".yaml", ".yml"}
YAML = {".yaml", ".yml"}
TOML = {".toml"}
MD = {".md", ".markdown", ".qmd"}
SPELL = (
    PY | BIOME | PRETTIER | TOML | MD | {".tex", ".typ", ".rs", ".txt", ".ps1", ".sh"}
)


def refresh_windows_path() -> None:
    """Pick up tools installed after Claude Code started (its PATH is a snapshot)."""
    if os.name != "nt":
        return
    import winreg

    parts = []
    for root, key in (
        (
            winreg.HKEY_LOCAL_MACHINE,
            r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment",
        ),
        (winreg.HKEY_CURRENT_USER, "Environment"),
    ):
        try:
            with winreg.OpenKey(root, key) as k:
                parts.append(os.path.expandvars(winreg.QueryValueEx(k, "Path")[0]))
        except OSError:
            pass
    os.environ["PATH"] = os.pathsep.join([*parts, os.environ.get("PATH", "")])


def find_up(start: Path, names: tuple[str, ...]) -> Path | None:
    """Nearest config file with one of `names` in `start` or its parents."""
    for folder in (start, *start.parents):
        for name in names:
            candidate = folder / name
            if candidate.is_file():
                return candidate
    return None


def run(cmd: list[str], cwd: Path) -> tuple[int, str]:
    exe = shutil.which(cmd[0])
    if exe is None:
        return 0, ""  # tool not installed: skip quietly
    try:
        proc = subprocess.run(
            [exe, *cmd[1:]],
            cwd=cwd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=TIMEOUT,
        )
    except subprocess.TimeoutExpired:
        return 1, f"{cmd[0]} timed out after {TIMEOUT}s"
    return proc.returncode, (proc.stdout + proc.stderr).strip()


def handle(path: Path) -> list[str]:
    ext, folder, issues = path.suffix.lower(), path.parent, []

    if ext in PY:
        own = find_up(folder, ("ruff.toml", ".ruff.toml"))
        cfg = [] if own else ["--config", str(LINT_DIR / "ruff.toml")]
        # fix first (e.g. drop unused imports), then format, then report what is left
        run(["ruff", "check", "--fix", "--quiet", *cfg, str(path)], folder)
        run(["ruff", "format", "--quiet", *cfg, str(path)], folder)
        code, out = run(
            ["ruff", "check", "--quiet", "--output-format", "concise", *cfg, str(path)],
            folder,
        )
        if code and out:
            issues.append(out)
        # type check only inside a uv project with a venv; standalone scripts
        # would only produce unresolved-import noise
        project = find_up(folder, ("pyproject.toml",))
        if project and (project.parent / ".venv").is_dir():
            code, out = run(
                ["ty", "check", "--output-format", "concise", str(path)],
                project.parent,
            )
            if code and out:
                issues.append(out)

    elif ext in BIOME:
        own = find_up(folder, ("biome.json", "biome.jsonc"))
        cfg = [] if own else ["--config-path", str(LINT_DIR)]
        code, out = run(
            ["biome", "check", "--write", "--no-errors-on-unmatched", *cfg, str(path)],
            folder,
        )
        if code and out:
            issues.append(out)

    elif ext in PRETTIER:
        own = find_up(
            folder,
            (
                ".prettierrc",
                ".prettierrc.json",
                ".prettierrc.yaml",
                "prettier.config.js",
            ),
        )
        cfg = [] if own else ["--config", str(LINT_DIR / ".prettierrc.json")]
        code, out = run(
            ["prettier", "--write", "--log-level", "warn", *cfg, str(path)], folder
        )
        if code and out:
            issues.append(out)
        if ext in YAML:
            own = find_up(folder, (".yamllint", ".yamllint.yaml", ".yamllint.yml"))
            code, out = run(
                [
                    "yamllint",
                    "-f",
                    "parsable",
                    "-c",
                    str(own or LINT_DIR / ".yamllint.yaml"),
                    str(path),
                ],
                folder,
            )
            if code and out:
                issues.append(out)

    elif ext in TOML:
        own = find_up(folder, (".taplo.toml", "taplo.toml"))
        code, out = run(
            [
                "taplo",
                "fmt",
                "--config",
                str(own or LINT_DIR / ".taplo.toml"),
                str(path),
            ],
            folder,
        )
        if code and out:
            issues.append(out)

    elif ext in MD:
        if ext == ".qmd":
            cfg = LINT_DIR / "qmd.markdownlint-cli2.jsonc"
        else:
            cfg = find_up(
                folder, (".markdownlint-cli2.jsonc", ".markdownlint-cli2.yaml")
            ) or (LINT_DIR / ".markdownlint-cli2.jsonc")
        # ':' marks a literal path (no glob expansion); run from the file's folder
        code, out = run(
            ["markdownlint-cli2", "--config", str(cfg), ":" + path.name], folder
        )
        if code and out:
            issues.append(
                "\n".join(
                    line
                    for line in out.splitlines()
                    if not line.startswith(
                        ("markdownlint-cli2 v", "Finding:", "Linting:", "Summary:")
                    )
                )
            )

    if ext in SPELL:
        own = find_up(folder, ("typos.toml", "_typos.toml", ".typos.toml"))
        code, out = run(
            [
                "typos",
                "--format",
                "brief",
                "--config",
                str(own or LINT_DIR / "typos.toml"),
                str(path),
            ],
            folder,
        )
        if code and out:
            issues.append(out)

    return [i for i in issues if i.strip()]


def main() -> int:
    if os.environ.get("CLAUDE_FORMAT_HOOK") == "0":
        return 0
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0
    tool_input = payload.get("tool_input") or {}
    tool_response = payload.get("tool_response") or {}
    raw = tool_input.get("file_path") or (
        tool_response.get("filePath") if isinstance(tool_response, dict) else None
    )
    if not raw:
        return 0
    path = Path(raw)
    if (
        not path.is_file()
        or path.name in SKIP_NAMES
        or SKIP_DIRS.intersection(path.parts)
    ):
        return 0
    if path.name.endswith((".min.js", ".min.css")):
        return 0

    refresh_windows_path()
    issues = handle(path)
    if not issues:
        return 0
    lines = "\n".join(issues).splitlines()
    if len(lines) > MAX_LINES:
        lines = [*lines[:MAX_LINES], f"... {len(lines) - MAX_LINES} more lines"]
    print(
        f"[format-hook] lint issues remain in {path}:\n" + "\n".join(lines),
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    sys.exit(main())
