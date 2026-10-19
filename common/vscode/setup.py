"""Install the shared VS Code settings and the per-use-case profiles.

profiles.json lists the extensions every profile gets ("base") and the extra ones of
each named profile. The named profiles share the Default profile's settings,
keybindings, snippets and tasks, so settings.jsonc here is the only settings file.
It is copied, not linked: VS Code writes machine-specific values (SSH hosts, DB
connections) into settings.json, and this repo is public.

    python setup.py            copy settings, create profiles, install missing extensions
    python setup.py --prune    also uninstall extensions that are not listed
    python setup.py --check    report drift only, change nothing (exit 1 on drift)
    python setup.py --diff     show how the live settings.json differs from the repo

Creating a profile edits VS Code's storage.json, so close VS Code first. The other
steps work while it is running.
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

HERE = Path(__file__).resolve().parent
SHARED = {
    "settings": True,
    "keybindings": True,
    "snippets": True,
    "tasks": True,
    "mcp": True,
}
EXTENSION_ID = re.compile(r"^[\w-]+\.[\w-]+$")


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


def sync_settings(user, check, stamp):
    src, dst = HERE / "settings.jsonc", user / "settings.json"
    if dst.exists() and dst.read_bytes() == src.read_bytes():
        print(f"ok       {dst}")
        return True
    if check:
        print(f"DRIFT    {dst} differs from the repo (see --diff)")
        return False
    if dst.exists():
        shutil.copy2(dst, dst.with_name(f"settings.json.bak-{stamp}"))
        print(f"backed up existing {dst}")
    user.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, dst)
    print(f"copied   {dst}")
    return True


def register_profiles(user, names, icons, check, sandbox, stamp):
    """Add missing profiles to VS Code's storage.json; return the names that exist."""
    storage = user / "globalStorage" / "storage.json"
    data = json.loads(storage.read_text(encoding="utf-8")) if storage.exists() else {}
    profiles = data.setdefault("userDataProfiles", [])
    have = {p["name"] for p in profiles}
    for p in profiles:
        if p["name"] in names and not (p.get("useDefaultFlags") or {}).get("settings"):
            print(
                f"WARN     profile '{p['name']}' has its own settings.json; the shared settings do not apply"
            )
    missing = [n for n in names if n not in have]
    if not missing:
        return set(names)
    if check:
        print(f"MISSING  profiles: {', '.join(missing)}")
        return have
    if not sandbox and vscode_running():
        print(f"SKIP     profiles {', '.join(missing)}: close VS Code, then re-run")
        return have
    if storage.exists():
        shutil.copy2(storage, storage.with_name(f"storage.json.bak-{stamp}"))
    for name in missing:
        location = "setups-" + re.sub(r"\W+", "-", name.lower())
        (user / "profiles" / location).mkdir(parents=True, exist_ok=True)
        profiles.append(
            {
                "location": location,
                "name": name,
                "icon": icons[name],
                "useDefaultFlags": SHARED,
            }
        )
        print(f"profile  {name}")
    storage.parent.mkdir(parents=True, exist_ok=True)
    storage.write_text(json.dumps(data, indent=4), encoding="utf-8")
    return set(names)


def sync_extensions(code, profile, wanted, prune, check):
    label = profile or "Default"
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
            code.run(
                profile, *[arg for e in extra for arg in ("--uninstall-extension", e)]
            )
            print(f"removed  {label}: {', '.join(extra)}")
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
        help="diff the live settings.json against the repo",
    )
    parser.add_argument(
        "--sandbox", type=Path, help="use a throwaway user-data and extensions folder"
    )
    args = parser.parse_args()

    user = user_dir(args.sandbox)
    if args.diff:
        live = user / "settings.json"
        repo = (
            (HERE / "settings.jsonc")
            .read_text(encoding="utf-8")
            .splitlines(keepends=True)
        )
        mine = (
            live.read_text(encoding="utf-8").splitlines(keepends=True)
            if live.exists()
            else []
        )
        sys.stdout.writelines(
            difflib.unified_diff(repo, mine, "repo settings.jsonc", str(live))
        )
        return 0

    config = json.loads((HERE / "profiles.json").read_text(encoding="utf-8"))
    base = [e.lower() for e in config["base"]]
    named = config["profiles"]
    stamp = time.strftime("%Y%m%d-%H%M%S")
    code = Code(args.sandbox)

    ok = sync_settings(user, args.check, stamp)
    icons = {name: p["icon"] for name, p in named.items()}
    present = register_profiles(
        user, list(named), icons, args.check, args.sandbox, stamp
    )
    ok &= sync_extensions(code, None, base, args.prune, args.check)
    for name, p in named.items():
        if name in present:
            ok &= sync_extensions(
                code,
                name,
                base + [e.lower() for e in p["extensions"]],
                args.prune,
                args.check,
            )
        else:
            ok = False
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
