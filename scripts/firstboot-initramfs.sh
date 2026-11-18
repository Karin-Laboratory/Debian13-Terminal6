#!/bin/sh
# SPDX-License-Identifier: MIT
# C-unit charter 1.2: unauthenticated SSH is strictly for physically isolated
# first installation on EMPTY P44; NEVER for rescue or an already installed OS.
set -eu
export PATH=/bin:/sbin:/usr/bin:/usr/sbin
root=/newroot
state="$root/.terminal6"
host="$state/ssh/dropbear_ed25519_host_key"
marker="$state/firstboot-complete"
pid=/run/terminal6-firstboot.pid
empty_p44() {
    [ -d "$root/lost+found" ] || return 1
    [ ! -e "$marker" ] && [ ! -e "$root/sbin/init" ] || return 1
    for entry in "$root"/* "$root"/.[!.]* "$root"/..?*; do
        [ -e "$entry" ] || continue
        case "$(basename "$entry")" in
            lost+found|.terminal6) ;; *) return 1 ;;
        esac
    done
    if [ -d "$state" ]; then
        for entry in "$state"/* "$state"/.[!.]* "$state"/..?*; do
            [ -e "$entry" ] || continue
            case "$(basename "$entry")" in
                ssh|inbox) ;; *) return 1 ;;
            esac
        done
    fi
    return 0
}
valid_credentials() {
    [ -x "$root/sbin/init" ] && [ -s "$root/etc/ssh/ssh_host_ed25519_key" ] || return 1
    if [ -s "$root/root/.ssh/authorized_keys" ]; then
        grep -Eq '^(ssh-ed25519|ecdsa-sha2-|ssh-rsa) ' "$root/root/.ssh/authorized_keys" && return 0
    fi
    [ -s "$root/etc/shadow" ] || return 1
    pw="$(awk -F: '$1=="root" {print $2}' "$root/etc/shadow")"
    case "$pw" in
        \$*) return 0 ;;
        *) return 1 ;;
    esac
}
setup_network() {
    count=0
    while [ "$count" -lt 20 ]; do
        [ -d /sys/class/net/lan2 ] && [ -d /sys/class/net/eth1 ] && break
        sleep 1
        count=$((count + 1))
    done
    [ -d /sys/class/net/lan2 ] && [ -d /sys/class/net/eth1 ] || {
        echo CUNIT_FIRSTBOOT_BLOCKED_MANAGEMENT_NIC_MISSING; return 1;
    }
    ip link set eth1 up
    ip link set lan2 up
    ip address add 192.168.1.1/24 dev lan2
}
case "$1" in
    probe)
        empty_p44
        ;;
    serve)
        empty_p44 || { echo CUNIT_FIRSTBOOT_FAIL_CLOSED_P44_NOT_EMPTY; exit 1; }
        mkdir -p -m 0700 "$state/ssh" "$state/inbox" /run
        chmod 0700 "$state" "$state/ssh" "$state/inbox"
        if [ ! -s "$host" ]; then
            /sbin/dropbearkey -t ed25519 -f "$host"
            chmod 0600 "$host"
            sync
        fi
        # RAM ONLY: do not change the persistent Debian password database.
        printf '%s\n' 'root::0:0:root:/root:/bin/sh' > /etc/passwd
        printf '%s\n' 'root::0:0:99999:7:::' > /etc/shadow
        chmod 0600 /etc/shadow
        setup_network || exit 1
        # -B allows blank password; binding is limited to the isolated IPv4.
        # No forwarding, routing, DHCP, bridging, or Wi-Fi is configured.
        /sbin/dropbear -B -j -k -E -r "$host" -p 192.168.1.1:22 -P "$pid"
        echo CUNIT_FIRSTBOOT_UNAUTH_SSH_ISOLATED_ONLY_192.168.1.1_22
        echo WARNING_ANY_PEER_ON_THIS_LINK_CAN_GET_ROOT
        while [ ! -f "$marker" ]; do
            sleep 2
            [ -s "$pid" ] && kill -0 "$(cat "$pid")" 2>/dev/null || {
                echo CUNIT_FIRSTBOOT_LISTENER_GONE; exit 1;
            }
        done
        valid_credentials || { echo CUNIT_FIRSTBOOT_REFUSE_BAD_CREDENTIALS; exit 1; }
        # Do not disconnect existing management session; stop the listener.
        if [ -s "$pid" ]; then kill "$(cat "$pid")" || true; fi
        printf '%s\n' 'root:x:0:0:root:/root:/bin/sh' > /etc/passwd
        printf '%s\n' 'root:!:0:0:99999:7:::' > /etc/shadow
        echo CUNIT_FIRSTBOOT_UNAUTH_LISTENER_CLOSED
        ;;
    finalize)
        # Manual operator gate after P44 installation and persistent auth setup.
        [ ! -e "$marker" ] || { echo CUNIT_FIRSTBOOT_ALREADY_FINISHED; exit 1; }
        valid_credentials || { echo CUNIT_FIRSTBOOT_BLOCKED_NO_P44_AUTH; exit 1; }
        printf '%s\n' 'P44_ROOT_AUTH_PRESENT_NO_UNAUTH_REENABLE' > "$state/firstboot-complete.tmp"
        chmod 0600 "$state/firstboot-complete.tmp"
        mv "$state/firstboot-complete.tmp" "$marker"
        sync
        [ -s "$marker" ] || exit 1
        echo CUNIT_FIRSTBOOT_P44_CREDENTIALS_SAVED
        ;;
    *) echo 'usage: terminal6-firstboot {probe|serve|finalize}' >&2; exit 2 ;;
esac
