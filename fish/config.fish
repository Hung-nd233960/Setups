# --- Alias: Setup alias for the fish config ---
alias ll="eza -a --icons always -l --color-scale-mode gradient -@ --smart-group --git --time-style '+%d-%m-%Y %H:%M' --classify=always --no-user"
alias cd="z"
alias ls="eza --icons always --no-user"
alias sdnow="shutdown now"
# --- SSH: Auto-launch zellij if not already inside ---
if test -n "$SSH_CONNECTION"
    if not set -q ZELLIJ
        exec zellij
    end
end

# --- Setup PATH carefully (only add if missing) ---
set -l default_path $HOME/.local/bin $HOME/.cargo/bin /usr/local/sbin /usr/local/bin /usr/bin /sbin /usr/sbin /bin
for p in $default_path
    if not contains $p $PATH
        set -gx PATH $p $PATH
    end
end

# --- direnv: load early and configure mode ---
direnv hook fish | source
set -g direnv_fish_mode eval_on_arrow

# --- Interactive session configuration ---
if status is-interactive
    if not set -q ZELLIJ
        exec zellij
    end
    # Other interactive-only commands go here
end

# --- zoxide: smart cd command ---
zoxide init fish | source

# --- oh-my-posh prompt ---
oh-my-posh init fish --config 'https://github.com/JanDeDobbeleer/oh-my-posh/blob/main/themes/catppuccin.omp.json' | source

# --- yazi wrapper function with cwd restore ---
function y
    set tmp (mktemp -t "yazi-cwd.XXXXXX")
    yazi $argv --cwd-file="$tmp"
    if read -z cwd <"$tmp"; and [ -n "$cwd" ]; and [ "$cwd" != "$PWD" ]
        builtin cd -- "$cwd"
    end
    rm -f -- "$tmp"
end
