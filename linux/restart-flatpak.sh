#!/usr/bin/env bash
# Restart the installed Doubao Murmur Flatpak and verify it stays running.

set -euo pipefail

app_id="com.doubao.Murmur"
state_dir="${XDG_STATE_HOME:-$HOME/.local/state}/doubao-murmur"
log_file="$state_dir/app.log"

mkdir -p "$state_dir"

if flatpak ps --columns=application | grep -Fxq "$app_id"; then
    flatpak kill "$app_id"
    for _ in {1..20}; do
        if ! flatpak ps --columns=application | grep -Fxq "$app_id"; then
            break
        fi
        sleep 0.1
    done
fi

printf '\n[%s] Starting %s\n' "$(date --iso-8601=seconds)" "$app_id" >> "$log_file"
nohup flatpak run "$app_id" >> "$log_file" 2>&1 < /dev/null &
launcher_pid=$!

for _ in {1..50}; do
    if flatpak ps --columns=application | grep -Fxq "$app_id"; then
        printf 'Doubao Murmur is running. Log: %s\n' "$log_file"
        exit 0
    fi
    if ! kill -0 "$launcher_pid" 2>/dev/null; then
        printf 'Doubao Murmur exited during startup. Log: %s\n' "$log_file" >&2
        tail -n 20 "$log_file" >&2
        exit 1
    fi
    sleep 0.1
done

printf 'Doubao Murmur did not become healthy. Log: %s\n' "$log_file" >&2
tail -n 20 "$log_file" >&2
exit 1
