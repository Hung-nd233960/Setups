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
    python setup.py --force    overwrite settings changed locally (kept otherwise)
    python setup.py --json     results as JSON instead of lines (setups-manager reads this)
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


RESULTS = None  # a list while --json collects results instead of printing them


def report(status, subject, detail=""):
    """One result: printed as a line, or collected for --json."""
    if RESULTS is not None:
        RESULTS.append(
            {"status": status.lower(), "subject": str(subject), "detail": detail}
        )
    else:
        print(f"{status:<8} {subject}" + (f": {detail}" if detail else ""))


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


def sync_file(src, dst, check, force, stamp):
    """Copy src over dst. A dst changed since the last copy (e.g. in the VS Code UI)
    is kept unless force, so local edits are never lost silently."""
    last = dst.with_name(dst.name + ".setups-installed")  # what the last run copied
    if dst.exists() and dst.read_bytes() == src.read_bytes():
        if not check and not (last.exists() and last.read_bytes() == src.read_bytes()):
            shutil.copyfile(src, last)
        report("ok", dst)
        return True
    edited = dst.exists() and last.exists() and dst.read_bytes() != last.read_bytes()
    if check or (edited and not force):
        why = "has local changes" if edited else "differs from the repo"
        report(
            "DRIFT",
            dst,
            f"{why}; --diff shows them, move what you want into the repo, then --force",
        )
        return False
    if dst.exists():
        shutil.copy2(dst, dst.with_name(f"{dst.name}.bak-{stamp}"))
        report("backup", dst)
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, dst)
    shutil.copyfile(src, last)
    report("copied", dst)
    return True


def update_storage(user, named, check, sandbox, stamp):
    """Register missing profiles and link marked projects to theirs in VS Code's
    storage.json. Returns the profile names that exist and whether all is in place."""
    storage = user / "globalStorage" / "storage.json"
    data = json.loads(storage.read_text(encoding="utf-8")) if storage.exists() else {}
    profiles = data.setdefault("userDataProfiles", [])
    for p in profiles:
        if p["name"] in named and not (p.get("useDefaultFlags") or {}).get("settings"):
            report(
                "WARN",
                f"profile {p['name']}",
                "has its own settings.json; the shared settings do not apply",
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
            report("WARN", folder, f"unknown profile '{name}' in .vscode/profile")
        elif links.get(folder_uri(folder)) != ids.get(name):
            relinks.append((folder, name))

    if not missing and not relinks:
        return set(named), True
    pending = [f"profile {n}" for n in missing] + [f"{f} -> {n}" for f, n in relinks]
    if check:
        for item in pending:
            report("MISSING", item)
        return existing, False
    if not sandbox and vscode_running():
        for item in pending:
            report("SKIP", item, "close VS Code, then re-run")
        return existing, False

    for name in missing:
        (user / "profiles" / ids[name]).mkdir(parents=True, exist_ok=True)
        report("profile", name)
    for folder, name in relinks:
        if name == DEFAULT:
            links.pop(folder_uri(folder), None)
        else:
            links[folder_uri(folder)] = ids[name]
        report("link", f"{folder} -> {name}")
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
            report("MISSING", label, ", ".join(missing))
            ok = False
        else:
            result = code.run(
                profile, *[arg for e in missing for arg in ("--install-extension", e)]
            )
            report("install", label, ", ".join(missing))
            if result.returncode:
                report("FAILED", label, (result.stdout + result.stderr).strip())
                ok = False
    if extra:
        if prune and not check:
            left = code.uninstall(profile, extra)
            removed = [e for e in extra if e not in left]
            if removed:
                report("removed", label, ", ".join(removed))
            if left:
                report("FAILED", label, "could not uninstall " + ", ".join(left))
                ok = False
        else:
            report("EXTRA", label, ", ".join(extra) + " (remove with --prune)")
            ok = False
    if not missing and not extra:
        report("ok", label, f"{len(wanted)} extensions")
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
    parser.add_argument(
        "--force",
        action="store_true",
        help="overwrite a settings file changed locally (a backup is kept)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="print the results as JSON (for setups-manager)",
    )
    args = parser.parse_args()

    global RESULTS
    if args.json:
        RESULTS = []
    status = run(args)
    if args.json:
        print(json.dumps({"ok": status == 0, "results": RESULTS}, indent=2))
    return status


def run(args):
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
    ok = sync_file(src, dst, args.check, args.force, stamp)
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
