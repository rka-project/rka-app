#!/usr/bin/env bash
set -euo pipefail

# This ordered companion preserves the upstream feature's metadata/SSH setup,
# replacing only its startup hook. Fail if feature ordering or packaging drifts.
test "$(id -u)" = 0
test -x /usr/local/share/ssh-init.sh
test -x /usr/sbin/sshd
test -x /usr/bin/ssh-keygen
if compgen -G '/etc/ssh/ssh_host_*_key*' > /dev/null; then
    echo "Refusing build-time SSH host identities; remove them in the install layer." >&2
    exit 1
fi
install -m 0755 ./ssh-init.sh /usr/local/share/ssh-init.sh
