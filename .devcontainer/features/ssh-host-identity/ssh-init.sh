#!/usr/bin/env bash
set -euo pipefail
umask 077

sudo_if_needed() {
    if [ "$(id -u)" -eq 0 ]; then
        "$@"
    else
        sudo -- "$@"
    fi
}

# -A creates only missing default host keys: distinct for a new container and
# stable when the same container restarts. No password or authorized key changes.
sudo_if_needed /usr/bin/ssh-keygen -A
sudo_if_needed /usr/sbin/sshd -t
sudo_if_needed /etc/init.d/ssh start
exec "$@"
