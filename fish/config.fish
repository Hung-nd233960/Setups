if status is-interactive
    function fish_greeting
        
        set user (whoami)

        # Time components
        set hour (date "+%H")
        set minute (date "+%M")
        set epoch (date "+%s")

        # AM / PM in Japanese
        if test $hour -lt 12
            set period 午前
        else
            set period 午後
        end
        
        if test $hour -lt 6
            set greeting おはようございます
        else if test $hour -lt 12
            set greeting おはようございます
        else if test $hour -lt 18
            set greeting こんにちは
        else
            set greeting こんばんは
        end

        # Convert hour to 12-hour format
        set hour12 (math "$hour % 12")
        if test $hour12 -eq 0
            set hour12 12
        end

        # Date components
        set year (date "+%Y")
        set month (date "+%-m")
        set day (date "+%-d")

        # Weekday (manual mapping, locale-independent)
        switch (date "+%u")
            case 1; set weekday 月曜日
            case 2; set weekday 火曜日
            case 3; set weekday 水曜日
            case 4; set weekday 木曜日
            case 5; set weekday 金曜日
            case 6; set weekday 土曜日
            case 7; set weekday 日曜日
        end

        echo "$greeting $user さん $period $hour12:$minute | $weekday $day 日 $month 月 $year 年"
        echo "epoch: $epoch"
    end

    # if running in VS Code's terminal, skip running zellij to avoid nested sessions
    
    # --- Alias: Setup alias for the fish config ---
    alias ll="eza -a --icons always -l --color-scale-mode gradient -@ --smart-group --git --time-style '+%d-%m-%Y %H:%M' --classify=always --no-user"
    alias cd="z"
    alias ls="eza --icons always --no-user"
    alias sdnow="shutdown now"

    alias vi="nvim"
    alias vim="nvim"
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
 
    # --- zoxide: smart cd command ---
    zoxide init fish | source


    # --- yazi wrapper function with cwd restore ---
    function y
        set tmp (mktemp -t "yazi-cwd.XXXXXX")
        yazi $argv --cwd-file="$tmp"
        if read -z cwd <"$tmp"; and [ -n "$cwd" ]; and [ "$cwd" != "$PWD" ]
            builtin cd -- "$cwd"
        end
        rm -f -- "$tmp"
    end
    source (/bin/starship init fish --print-full-init | psub)
end

