#!/bin/sh
# SPDX-License-Identifier: MIT
# Emergency SSH ONLY after P44 handoff has failed. Isolated wired LAN only.
# Requires owner-private authorized_keys and a persistent, pinned host key.
set -eu
export PATH=/bin:/sbin
if [ ! -s /root/.ssh/authorized_keys ] || [ ! -s /etc/dropbear/dropbear_ed25519_host_key ]; then
    echo 'TERMINAL6_RESCUE_SSH_DISABLED_NO_PRIVATE_IDENTITY'
    exit 0
fi
# No automatic activation on the home LAN. This flag MUST be deliberately
# created during owner-private manufacture for an isolated direct cable.
if [ ! -f /etc/dropbear/ISOLATED_MANAGEMENT_ONLY ]; then
    echo 'TERMINAL6_RESCUE_SSH_DISABLED_NOT_ISOLATED'
    exit 0
fi
# Support later non-overlapping IP selection by a private configuration file;
# never change hardware or bootloader IP in this script.
rescue_ip=192.168.3.1
rescue_prefix=24
if [ -r /etc/dropbear/management-ip ]; then
    IFS=/ read -r rescue_ip rescue_prefix < /etc/dropbear/management-ip
fi
case "$rescue_ip" in
    *[!0-9.]*|'') echo 'TERMINAL6_RESCUE_IP_INVALID'; exit 1 ;;
esac
case "$rescue_prefix" in 24|25|26|27|28|29|30) ;; *) echo 'TERMINAL6_RESCUE_PREFIX_INVALID'; exit 1 ;; esac
# Linux built-in NETSYS/DSA must expose the experimentally identified LAN.
n=0
while [ "$n" -lt 20 ]; do
    [ -d /sys/class/net/lan2 ] && [ -d /sys/class/net/eth1 ] && break
    sleep 1
    n=$((n+1))
done
[ -d /sys/class/net/lan2 ] && [ -d /sys/class/net/eth1 ] || {
    echo 'TERMINAL6_RESCUE_SSH_BLOCKED_BUILTIN_LAN_MISSING'
    exit 1
}
ip link set eth1 up
ip link set lan2 up
ip address add "$rescue_ip/$rescue_prefix" dev lan2
mkdir -p /run
# Separate 2222 host-key identity from Debian's normal SSH on port 22.
# -s/-g: no password auth, -j/-k: no TCP forwarding, -E: console logging.
/sbin/dropbear -s -g -j -k -E -r /etc/dropbear/dropbear_ed25519_host_key \
    -p "$rescue_ip:2222" -P /run/terminal6-dropbear.pid
echo 'TERMINAL6_RESCUE_SSH_STARTED_ISOLATED_PORT_2222'
