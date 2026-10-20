"""Install the shared VS Code settings and the per-use-case profiles.

profiles.json lists the extensions every profile gets ("base") and the extra ones of
each named profile; "extends" adds another profile's list. The named profiles share
the Default profile's settings, keybindings, snippets and tasks, so settings.jsonc
here is the only settings file. It is copied, not linked: VS Code writes
machine-specific values (SSH hosts, DB connections) into settings.json, and this
repo is public.

Projects name their profile in .vscode/profile (written by new-project or
`vsc --set`). Each run links those in the projects folder to their profile, so
File > Open picks it too.

    python setup.py            copy settings, create profiles, link projects, install extensions
    python setup.py --prune    also uninstall extensions that are not listed
    python setup.py --check    report drift only, change nothing (exit 1 on drift)
    python setup.py --diff     show how the live settings.json differs from the repo
    python setup.py --server   on an SSH host you control: install remote.jsonc as its
                               remote settings (combine with --check / --diff)

Creating profiles and linking projects edit VS Code's storage.json, so close VS Code
first. The other steps work while it is running.
"""

import argparse
import difflib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import quote

HERE = Path(__file__).resolve().parent
SHARED = {
    "settings": True,
    "keybindings": True,
    "snippets": True,
    "tasks": True,
    "mcp": True,
}
EXTENSION_ID = re.compile(r"^[\w-]+\.[\w-]+$")
DEFAULT = "Default"


def user_dir(sandbox):
    if sandbox:
        return sandbox / "ud" / "User"
    if sys.platform == "win32":
        return Path(os.environ["APPDATA"]) / "Code" / "User"
    return (
        Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
        / "Code"
        / "User"
    )


def projects_root():
    """Same rule as new-project: $NEW_PROJECT_DIR, else D:\\Personal Projects, else ~/Projects."""
    if env := os.environ.get("NEW_PROJECT_DIR"):
        return Path(env)
    windows_default = Path(r"D:\Personal Projects")
    return windows_default if windows_default.is_dir() else Path.home() / "Projects"


def marked_projects():
    """(folder, profile name) for each project whose .vscode/profile names one."""
    root = projects_root()
    if not root.is_dir():
        return []
    markers = sorted(root.glob("*/.vscode/profile"))
    return [(m.parent.parent, m.read_text(encoding="utf-8").strip()) for m in markers]


def folder_uri(folder):
    """The key VS Code uses for a folder: file:///d%3A/Personal%20Projects/x."""
    path = folder.resolve().as_posix()
    if re.match(r"^[A-Za-z]:", path):
        path = "/" + path[0].lower() + path[1:]
    return "file://" + quote(path, safe="/")


def vscode_running():
    if sys.platform == "win32":
        out = subprocess.run(
            ["tasklist", "/FI", "IMAGENAME eq Code.exe", "/NH"],
            capture_output=True,
            text=True,
        ).stdout
        return "Code.exe" in out
    return subprocess.run(["pgrep", "-x", "code"], capture_output=True).returncode == 0


class Code:
    """The `code` CLI, optionally pointed at a throwaway sandbox."""

    def __init__(self, sandbox):
        exe = shutil.which("code")
        if not exe:
            sys.exit("VS Code's 'code' command is not on PATH")
        self.cmd = [exe]
        self.ext_dir = Path.home() / ".vscode" / "extensions"
        if sandbox:
            self.cmd += [
                "--user-data-dir",
                str(sandbox / "ud"),
                "--extensions-dir",
                str(sandbox / "ext"),
            ]
            self.ext_dir = sandbox / "ext"

    def run(self, profile, *args):
        cmd = self.cmd + (["--profile", profile] if profile else []) + list(args)
        return subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")

    def uninstall(self, profile, ids):
        """Uninstall one at a time (the CLI stops a batch at the first refusal) and
        repeat, so an extension goes once its dependents are gone. Returns leftovers."""
        left = list(ids)
        while left:
            for e in left:
                self.run(profile, "--uninstall-extension", e)
            still = [e for e in left if e in self.installed(profile)]
            if len(still) == len(left):
                break
            left = still
        return left

    def installed(self, profile):
        lines = self.run(profile, "--list-extensions").stdout.splitlines()
        return {
            line.strip().lower() for line in lines if EXTENSION_ID.match(line.strip())
        }

    def dependencies(self, ids):
        """Extensions the given ones require (extensionDependencies); never pruned."""
        deps, todo = set(), list(ids)
        while todo:
            for manifest in self.ext_dir.glob(f"{todo.pop()}-[0-9]*/package.json"):
                for dep in json.loads(manifest.read_text(encoding="utf-8")).get(
                    "extensionDependencies", []
                ):
                    if dep.lower() not in deps:
                        deps.add(dep.lower())
                        todo.append(dep.lower())
        return deps


def profile_extensions(named, name):
    """A profile's own extensions plus those of the profile it extends, if any."""
    p = named[name]
    parent = profile_extensions(named, p["extends"]) if "extends" in p else []
    return parent + [e.lower() for e in p["extensions"] if e.lower() not in parent]


def sync_file(src, dst, check, stamp):
    """Copy src over dst, backing up a different dst first."""
    if dst.exists() and dst.read_bytes() == src.read_bytes():
        print(f"ok       {dst}")
        return True
    if check:
        print(f"DRIFT    {dst} differs from the repo (see --diff)")
        return False
    if dst.exists():
        shutil.copy2(dst, dst.with_name(f"{dst.name}.bak-{stamp}"))
        print(f"backed up existing {dst}")
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, dst)
    print(f"copied   {dst}")
    return True


def update_storage(user, named, check, sandbox, stamp):
    """Register missing profiles and link marked projects to theirs in VS Code's
    storage.json. Returns the profile names that exist and whether all is in place."""
    storage = user / "globalStorage" / "storage.json"
    data = json.loads(storage.read_text(encoding="utf-8")) if storage.exists() else {}
    profiles = data.setdefault("userDataProfiles", [])
    for p in profiles:
        if p["name"] in named and not (p.get("useDefaultFlags") or {}).get("settings"):
            print(
                f"WARN     profile '{p['name']}' has its own settings.json; the shared settings do not apply"
            )
    existing = {p["name"] for p in profiles}
    missing = [n for n in named if n not in existing]
    for name in missing:
        location = "setups-" + re.sub(r"\W+", "-", name.lower())
        profiles.append(
            {
                "location": location,
                "name": name,
                "icon": named[name]["icon"],
                "useDefaultFlags": SHARED,
            }
        )
    ids = {p["name"]: p["location"] for p in profiles}

    associations = data.setdefault("profileAssociations", {})
    links = associations.setdefault("workspaces", {})
    associations.setdefault("emptyWindows", {})
    relinks = []
    for folder, name in marked_projects():
        if name != DEFAULT and name not in ids:
            print(f"WARN     {folder}: unknown profile '{name}' in .vscode/profile")
        elif links.get(folder_uri(folder)) != ids.get(name):
            relinks.append((folder, name))

    if not missing and not relinks:
        return set(named), True
    pending = [f"profile {n}" for n in missing] + [f"{f} -> {n}" for f, n in relinks]
    if check:
        print("MISSING  " + "\n         ".join(pending))
        return existing, False
    if not sandbox and vscode_running():
        print(
            "SKIP     close VS Code, then re-run for:\n         "
            + "\n         ".join(pending)
        )
        return existing, False

    for name in missing:
        (user / "profiles" / ids[name]).mkdir(parents=True, exist_ok=True)
        print(f"profile  {name}")
    for folder, name in relinks:
        if name == DEFAULT:
            links.pop(folder_uri(folder), None)
        else:
            links[folder_uri(folder)] = ids[name]
        print(f"link     {folder} -> {name}")
    if storage.exists():
        shutil.copy2(storage, storage.with_name(f"storage.json.bak-{stamp}"))
    storage.parent.mkdir(parents=True, exist_ok=True)
    storage.write_text(json.dumps(data, indent=4), encoding="utf-8")
    return set(named), True


def sync_extensions(code, profile, wanted, prune, check):
    label = profile or DEFAULT
    have = code.installed(profile)
    missing = [e for e in wanted if e not in have]
    extra = sorted(have - set(wanted) - code.dependencies(wanted))
    ok = True
    if missing:
        if check:
            print(f"MISSING  {label}: {', '.join(missing)}")
            ok = False
        else:
            result = code.run(
                profile, *[arg for e in missing for arg in ("--install-extension", e)]
            )
            print(f"install  {label}: {', '.join(missing)}")
            if result.returncode:
                print(result.stdout + result.stderr)
                ok = False
    if extra:
        if prune and not check:
            left = code.uninstall(profile, extra)
            removed = [e for e in extra if e not in left]
            if removed:
                print(f"removed  {label}: {', '.join(removed)}")
            if left:
                print(f"FAILED   {label}: could not uninstall {', '.join(left)}")
                ok = False
        else:
            print(f"EXTRA    {label}: {', '.join(extra)} (remove with --prune)")
            ok = False
    if not missing and not extra:
        print(f"ok       {label}: {len(wanted)} extensions")
    return ok


def main():
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--prune", action="store_true", help="uninstall extensions that are not listed"
    )
    parser.add_argument(
        "--check", action="store_true", help="report drift only, change nothing"
    )
    parser.add_argument(
        "--diff",
        action="store_true",
        help="diff the live settings file against the repo",
    )
    parser.add_argument(
        "--server",
        action="store_true",
        help="install the remote settings on this SSH host",
    )
    parser.add_argument(
        "--sandbox", type=Path, help="use a throwaway user-data and extensions folder"
    )
    args = parser.parse_args()

    user = user_dir(args.sandbox)
    if args.server:
        src, dst = (
            HERE / "remote.jsonc",
            Path.home() / ".vscode-server" / "data" / "Machine" / "settings.json",
        )
    else:
        src, dst = HERE / "settings.jsonc", user / "settings.json"
    if args.diff:
        repo = src.read_text(encoding="utf-8").splitlines(keepends=True)
        live = (
            dst.read_text(encoding="utf-8").splitlines(keepends=True)
            if dst.exists()
            else []
        )
        sys.stdout.writelines(
            difflib.unified_diff(repo, live, f"repo {src.name}", str(dst))
        )
        return 0

    stamp = time.strftime("%Y%m%d-%H%M%S")
    ok = sync_file(src, dst, args.check, stamp)
    if args.server:
        return 0 if ok else 1

    config = json.loads((HERE / "profiles.json").read_text(encoding="utf-8"))
    base = [e.lower() for e in config["base"]]
    named = config["profiles"]
    code = Code(args.sandbox)
    present, linked = update_storage(user, named, args.check, args.sandbox, stamp)
    ok &= linked
    ok &= sync_extensions(code, None, base, args.prune, args.check)
    for name in named:
        if name in present:
            ok &= sync_extensions(
                code,
                name,
                base + profile_extensions(named, name),
                args.prune,
                args.check,
            )
        else:
            ok = False
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
