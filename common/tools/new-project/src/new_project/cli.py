"""new-project: create a project folder with this machine's conventions.

    new-project py      my-tool       Python package / CLI (uv, src layout, pytest)
    new-project data    ecg-hrv       data analysis (uv env, data/, notebooks/, Quarto report)
    new-project report  thesis-ch2    report / paper (Quarto; --engine typst|latex)
    new-project web     lab-page      static web page (HTML/CSS/JS, no build step)

Templates live in templates/<layer>/ as *.tmpl files; {{placeholders}} are filled in,
"__module__" in paths becomes the Python module name.
"""

import argparse
import datetime
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

from new_project import __version__

TEMPLATES = Path(__file__).parent / "templates"
REFERENCES = Path.home() / "Documents" / "References"
NAME_RE = re.compile(r"^[a-z][a-z0-9]*(-[a-z0-9]+)*$")

TYPES = {
    "py": "Python package / CLI (uv, src layout, pytest)",
    "data": "Data analysis / research (uv env, data/, notebooks/, Quarto report)",
    "report": "Report / paper (Quarto by default; --engine typst or latex)",
    "web": "Static web page (HTML/CSS/JS, no build step)",
}
UV_TYPES = {"py", "data"}


def default_root() -> Path:
    if env := os.environ.get("NEW_PROJECT_DIR"):
        return Path(env)
    windows_default = Path(r"D:\Personal Projects")
    return windows_default if windows_default.is_dir() else Path.home() / "Projects"


def git_user() -> str:
    try:
        out = subprocess.run(
            ["git", "config", "user.name"], capture_output=True, text=True, check=False
        )
        return out.stdout.strip() or "Author"
    except OSError:
        return "Author"


def layers(kind: str, engine: str) -> list[str]:
    if kind == "report":
        return ["common", f"report-{engine}"]
    return ["common", kind]


def collect(kind: str, engine: str) -> dict[str, Path]:
    """Relative template path -> source file; later layers override earlier ones."""
    files: dict[str, Path] = {}
    for layer in layers(kind, engine):
        root = TEMPLATES / layer
        for src in sorted(root.rglob("*")):
            if src.is_file():
                files[src.relative_to(root).as_posix()] = src
    return files


def render(text: str, ctx: dict[str, str]) -> str:
    for key, value in ctx.items():
        text = text.replace("{{" + key + "}}", value)
    return text


def run(cmd: list[str], cwd: Path) -> None:
    print(f"  $ {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        print(result.stdout + result.stderr, file=sys.stderr)
        raise SystemExit(f"error: '{cmd[0]}' failed (exit {result.returncode})")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="new-project",
        description="Create a project with git, a CLAUDE.md, a README and the machine's lint setup.",
        epilog="Types: " + "; ".join(f"{k} = {v}" for k, v in TYPES.items()),
    )
    parser.add_argument("type", choices=TYPES, help="project type")
    parser.add_argument(
        "name", help="folder/package name: lowercase words joined by hyphens"
    )
    parser.add_argument(
        "--dir",
        type=Path,
        default=None,
        help=f"parent folder (default: {default_root()})",
    )
    parser.add_argument("--description", default="", help="one-line description")
    parser.add_argument(
        "--engine",
        choices=["quarto", "typst", "latex"],
        default="quarto",
        help="report engine",
    )
    parser.add_argument(
        "--no-git", action="store_true", help="skip git init and first commit"
    )
    parser.add_argument(
        "--no-sync", action="store_true", help="skip 'uv sync' for Python projects"
    )
    parser.add_argument(
        "--version", action="version", version=f"%(prog)s {__version__}"
    )
    args = parser.parse_args(argv)

    if not NAME_RE.match(args.name):
        parser.error(
            "name must be lowercase letters/digits in words joined by hyphens, e.g. ecg-hrv"
        )
    target = (args.dir or default_root()) / args.name
    if target.exists() and any(target.iterdir()):
        parser.error(f"{target} already exists and is not empty")

    today = datetime.date.today()
    library = REFERENCES / "library.bib"
    ctx = {
        "name": args.name,
        "module": args.name.replace("-", "_"),
        "title": args.name.replace("-", " ").title(),
        "description": args.description
        or f"{args.name.replace('-', ' ').capitalize()}.",
        "author": git_user(),
        "date": today.isoformat(),
        "year": str(today.year),
        # Quarto/LaTeX read the user's Zotero export directly; Typst cannot reach
        # files outside the project, so it always uses a local references.bib
        "bibliography": library.as_posix() if library.is_file() else "references.bib",
        "csl": (REFERENCES / "csl" / "vancouver.csl").as_posix(),
    }

    print(f"Creating {args.type} project at {target}")
    for rel, src in collect(args.type, args.engine).items():
        out_rel = render(rel.replace("__module__", ctx["module"]), ctx)
        if out_rel.endswith(".tmpl"):
            out_rel = out_rel[: -len(".tmpl")]
        out = target / out_rel
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(
            render(src.read_text(encoding="utf-8"), ctx), encoding="utf-8", newline="\n"
        )

    if (
        args.type == "report"
        and args.engine != "typst"
        and ctx["bibliography"] == "references.bib"
    ):
        print(
            "  note: no Zotero export at ~/Documents/References/library.bib yet; using local references.bib"
        )

    if args.type in UV_TYPES and not args.no_sync:
        if shutil.which("uv") is None:
            print("  warning: uv not found; run 'uv sync' later", file=sys.stderr)
        else:
            run(["uv", "sync", "--quiet"], target)

    if not args.no_git:
        run(["git", "init", "-q", "-b", "main"], target)
        run(["git", "add", "-A"], target)
        run(
            [
                "git",
                "commit",
                "-q",
                "-m",
                f"Initial scaffold (new-project {args.type})",
            ],
            target,
        )

    print(
        f'\nDone. Next: cd "{target}"  then read README.md (and CLAUDE.md for agents).'
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
