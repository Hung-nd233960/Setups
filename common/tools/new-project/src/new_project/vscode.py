"""vsc: open a project in its VS Code profile, or set that profile.

    vsc [dir]                    open dir with the profile named in dir/.vscode/profile
    vsc --set <profile> [dir]    write .vscode/profile (and .vscode/extensions.json)
    vsc --list                   list the profiles

Profiles and their extensions come from Setups/common/vscode/profiles.json.
Opening with `code --profile` also makes VS Code remember the profile for the folder;
Setups' setup.py links all marked projects while VS Code is closed.
"""

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

# Editable install: src/new_project -> Setups/common/vscode
PROFILES_JSON = Path(__file__).resolve().parents[4] / "vscode" / "profiles.json"
DEFAULT = "Default"
TYPE_PROFILES = {"py": "Python", "data": "Data Science", "report": "Docs", "web": "Web"}


def profiles() -> dict[str, dict]:
    if not PROFILES_JSON.is_file():
        return {}
    return json.loads(PROFILES_JSON.read_text(encoding="utf-8"))["profiles"]


def names() -> list[str]:
    """Profile names, or [] when profiles.json is out of reach (non-editable install)."""
    named = profiles()
    return [DEFAULT, *named] if named else []


def extensions(name: str) -> list[str]:
    """A profile's own extensions plus those of the profile it extends (Default: none)."""
    named = profiles()
    if name not in named:
        return []
    p = named[name]
    parent = extensions(p["extends"]) if "extends" in p else []
    return parent + [e for e in p["extensions"] if e not in parent]


def read_marker(folder: Path) -> str | None:
    marker = folder / ".vscode" / "profile"
    return marker.read_text(encoding="utf-8").strip() if marker.is_file() else None


def write_marker(folder: Path, name: str) -> None:
    """Write .vscode/profile and add the profile's extensions to the recommendations."""
    vscode = folder / ".vscode"
    vscode.mkdir(parents=True, exist_ok=True)
    (vscode / "profile").write_text(name + "\n", encoding="utf-8", newline="\n")
    wanted = extensions(name)
    if not wanted:
        return
    recs_file = vscode / "extensions.json"
    try:
        recs = (
            json.loads(recs_file.read_text(encoding="utf-8"))
            if recs_file.exists()
            else {}
        )
    except json.JSONDecodeError:
        print(f"  note: left {recs_file} alone (not plain JSON)", file=sys.stderr)
        return
    current = recs.get("recommendations", [])
    recs["recommendations"] = current + [e for e in wanted if e not in current]
    recs_file.write_text(
        json.dumps(recs, indent=2) + "\n", encoding="utf-8", newline="\n"
    )


def open_folder(folder: Path, name: str) -> int:
    code = shutil.which("code")
    if code is None:
        print("error: VS Code's 'code' command is not on PATH", file=sys.stderr)
        return 1
    return subprocess.run(
        [code, "--profile", name, str(folder)], check=False
    ).returncode


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="vsc",
        description="Open a project in its VS Code profile, or set that profile.",
    )
    parser.add_argument(
        "dir",
        nargs="?",
        type=Path,
        default=Path.cwd(),
        help="project folder (default: here)",
    )
    parser.add_argument(
        "--set", metavar="PROFILE", choices=names() or None, help="write the marker"
    )
    parser.add_argument("--list", action="store_true", help="list the profiles")
    args = parser.parse_args(argv)

    if not names():
        parser.error(f"profiles.json not found at {PROFILES_JSON}")
    if args.list:
        for name in names():
            print(f"{name:<14} {', '.join(extensions(name)) or 'base extensions only'}")
        return 0
    folder = args.dir.resolve()
    if args.set:
        write_marker(folder, args.set)
        print(f"{folder}: VS Code profile set to {args.set}")
        return 0
    name = read_marker(folder)
    if name is None:
        print(
            f"note: no .vscode/profile in {folder}; opening with {DEFAULT}",
            file=sys.stderr,
        )
    return open_folder(folder, name or DEFAULT)


if __name__ == "__main__":
    raise SystemExit(main())
