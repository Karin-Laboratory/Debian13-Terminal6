#!/bin/sh
# SPDX-License-Identifier: MIT
# Debian P44 firstboot credential handoff; never run from P25/initramfs.
# Charter v1.4: a physically isolated cable is a REQUIRED human prerequisite.
set -eu
export PATH=/usr/sbin:/usr/bin:/sbin:/bin
state=/var/lib/terminal6
done_marker="$state/firstboot-complete"
verified="$state/firstboot-auth-verified"
dropkey=/etc/dropbear/dropbear_ed25519_host_key

root_has_credentials() {
    [ -s /etc/ssh/ssh_host_ed25519_key ] || return 1
    pw="$(awk -F: '$1=="root" { print $2 }' /etc/shadow)"
    case "$pw" in
        '$'*) return 0 ;;
    esac
    if [ -s /root/.ssh/authorized_keys ]; then
        [ "$(stat -c %a /root/.ssh)" = 700 ] || return 1
        [ "$(stat -c %a /root/.ssh/authorized_keys)" = 600 ] || return 1
        grep -Eq '^(ssh-ed25519|ecdsa-sha2-|ssh-rsa) ' /root/.ssh/authorized_keys && return 0
    fi
    return 1
}

case "$1" in
    prepare)
        [ ! -e "$done_marker" ] || exit 1
        mkdir -p -m 0700 "$state" /etc/dropbear
        chmod 0700 "$state"
        # Host identity belongs to each physical P44, not the archive.
        [ -s /etc/ssh/ssh_host_ed25519_key ] || ssh-keygen -q -t ed25519 -N '' -f /etc/ssh/ssh_host_ed25519_key
        chmod 0600 /etc/ssh/ssh_host_ed25519_key
        if [ ! -s "$dropkey" ]; then
            dropbearconvert openssh dropbear /etc/ssh/ssh_host_ed25519_key "$dropkey"
            chmod 0600 "$dropkey"
        fi
        ssh-keygen -lf /etc/ssh/ssh_host_ed25519_key
        sync
        echo 'WARNING: FIRSTBOOT BLANK-PASSWORD ROOT SSH IS PERMITTED ONLY ON A PHYSICALLY ISOLATED WIRED LAN'
        echo 'WARNING: ANY UNTRUSTED PEER ON THIS LINK CAN LOG IN AS ROOT'
        ;;
    verify-start)
        [ ! -e "$done_marker" ] || { echo CUNIT_ALREADY_PROVISIONED; exit 1; }
        root_has_credentials || { echo CUNIT_FIRSTBOOT_NO_PERSISTENT_CREDENTIALS; exit 1; }
        # Test real Debian authenticated sshd independently on port 2223.
        systemctl start terminal6-authcheck.service
        echo 'From a DIFFERENT SESSION: ssh -p 2223 root@192.168.1.1'
        echo 'After authenticating: touch /var/lib/terminal6/firstboot-auth-verified'
        ;;
    finalize)
        [ ! -e "$done_marker" ] || { echo CUNIT_ALREADY_PROVISIONED; exit 1; }
        root_has_credentials || { echo CUNIT_FIRSTBOOT_NO_PERSISTENT_CREDENTIALS; exit 1; }
        [ -f "$verified" ] || { echo CUNIT_FIRSTBOOT_NO_VERIFIED_SECOND_SESSION; exit 1; }
        # Key-only initial configuration must also lock the original empty
        # system root password. OpenSSH public-key access remains available.
        root_pw="$(awk -F: '$1=="root" { print $2 }' /etc/shadow)"
        if [ -z "$root_pw" ]; then
            [ -s /root/.ssh/authorized_keys ] || exit 1
            passwd -l root >/dev/null
            [ "$(awk -F: '$1=="root" { print $2 }' /etc/shadow)" != "" ] || exit 1
            sync
        fi
        # Only main Dropbear listener stops; authenticated setup child stays
        # alive while normal OpenSSH port 22 comes up without a reboot.
        umask 077
        printf '%s\n' 'AUTHENTICATED_ROOT_SSH_VERIFIED_DISABLE_UNAUTH_FOREVER' > "$state/firstboot-complete.tmp"
        mv "$state/firstboot-complete.tmp" "$done_marker"
        sync
        systemctl disable terminal6-firstboot.service
        systemctl stop terminal6-firstboot.service
        systemctl enable ssh.service
        systemctl start ssh.service
        systemctl stop terminal6-authcheck.service || true
        echo CUNIT_FIRSTBOOT_CLOSED_NORMAL_AUTHENTICATED_SSH_STARTED
        ;;
    *) echo 'usage: terminal6-p44-firstboot {prepare|verify-start|finalize}' >&2; exit 2 ;;
esac
