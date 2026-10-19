#!/usr/bin/env bash
# Link this repo's configs into place on Linux. Safe to re-run.
# Existing non-link targets are renamed to <name>.bak-<timestamp>, never deleted.
set -euo pipefail

repo="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
stamp="$(date +%Y%m%d-%H%M%S)"
config="${XDG_CONFIG_HOME:-$HOME/.config}"

link() {
  local target="$1" link="$2"
  if [ -L "$link" ] && [ "$(readlink "$link")" = "$target" ]; then
    echo "ok       $link"
    return
  fi
  if [ -L "$link" ]; then
    rm "$link"
  elif [ -e "$link" ]; then
    mv "$link" "$link.bak-$stamp"
    echo "backed up existing $link"
  fi
  mkdir -p "$(dirname "$link")"
  ln -s "$target" "$link"
  echo "linked   $link -> $target"
}

# Shared with Windows
link "$repo/common/nvim" "$config/nvim"
link "$repo/common/yazi" "$config/yazi"
link "$repo/common/helix" "$config/helix"
link "$repo/common/starship/starship.toml" "$config/starship.toml"

# Linux only
link "$repo/linux/fish" "$config/fish"
link "$repo/linux/kitty" "$config/kitty"
link "$repo/linux/btop" "$config/btop"
link "$repo/linux/zellij" "$config/zellij"

# Git: global ignore and line endings
link "$repo/common/git/ignore" "$config/git/ignore"
git config --global core.autocrlf input
echo "set      git core.autocrlf=input"

# VS Code: settings are copied, not linked (VS Code writes machine-specific values into them)
if command -v code >/dev/null; then
  python3 "$repo/common/vscode/setup.py" || echo "VS Code setup reported problems (see above)"
fi

# Lint/format defaults in the home folder (tools search parent folders)
for name in .editorconfig ruff.toml biome.json .prettierrc.json .yamllint.yaml .taplo.toml .markdownlint-cli2.jsonc typos.toml; do
  link "$repo/common/lint/$name" "$HOME/$name"
done
