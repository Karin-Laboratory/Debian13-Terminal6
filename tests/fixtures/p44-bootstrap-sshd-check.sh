#!/bin/sh
# SPDX-License-Identifier: MIT
# Build-only check. Never starts sshd or writes account credentials.
set -eu
[ "$#" -eq 1 ] && [ "$1" = /run/t6-bootstrap-ci.conf ] || exit 2
for client in \
    'user=t6-enroll,addr=192.168.1.50,host=fixture,laddr=192.168.1.1,lport=2224' \
    'user=t6-enroll,addr=192.168.1.51,host=fixture,laddr=192.168.1.1,lport=2224' \
    'user=root,addr=192.168.1.50,host=fixture,laddr=192.168.1.1,lport=2224' \
    'user=other,addr=192.168.1.50,host=fixture,laddr=192.168.1.1,lport=2224'
do
    state=$(/usr/sbin/sshd -T -f "$1" -C "$client")
    case "$client" in
        user=t6-enroll,addr=192.168.1.50,*) extra='passwordauthentication yes
authenticationmethods password' ;;
        *) extra='passwordauthentication no' ;;
    esac
    for rule in 'addressfamily inet' 'permitrootlogin no' 'permitemptypasswords no' \
        'pubkeyauthentication no' 'kbdinteractiveauthentication no' 'disableforwarding yes' \
        'permittty no' 'allowusers t6-enroll@192.168.1.50' \
        'forcecommand /usr/local/libexec/terminal6-enroll-key'
    do
        printf '%s\n' "$state" | grep -Fxq "$rule" || exit 1
    done
    printf '%s\n' "$extra" | while IFS= read -r rule; do
        printf '%s\n' "$state" | grep -Fxq "$rule" || exit 1
    done
    [ "$(printf '%s\n' "$state" | awk '$1 == "listenaddress"')" = 'listenaddress 192.168.1.1:2224' ]
done
printf '%s\n' 'P44_BOOTSTRAP_POLICY_OFFLINE_PASS'
