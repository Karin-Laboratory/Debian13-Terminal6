#!/bin/sh
# SPDX-License-Identifier: MIT
# Inspect the effective SSH policy, without starting a daemon or changing credentials.
set -eu
[ "$#" -eq 1 ] && [ "$1" = check ] || { echo 'usage: terminal6-p44-firstboot check' >&2; exit 2; }
state=$(/usr/sbin/sshd -T -C user=root,host=terminal6-debian,addr=192.168.1.50,laddr=192.168.1.1,lport=22)
for rule in 'passwordauthentication no' 'kbdinteractiveauthentication no' 'permitrootlogin no' 'permitemptypasswords no' 'pubkeyauthentication yes' 'authenticationmethods publickey' 'disableforwarding yes'; do
    printf '%s\n' "$state" | grep -Fxq "$rule" || { echo "unexpected SSH policy: $rule" >&2; exit 1; }
done
[ "$(printf '%s\n' "$state" | awk '$1 == "listenaddress"')" = 'listenaddress 192.168.1.1:22' ]
printf '%s\n' 'P44_EFFECTIVE_SSHD_KEY_ONLY_AND_NO_ROOT_PASS'
