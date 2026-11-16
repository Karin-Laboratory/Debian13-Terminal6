#!/bin/sh
# SPDX-License-Identifier: MIT
# PUBLIC-source Linux NETSYS/MT7531/PCS management readiness gate.
# No private test23/test24 modules, manual MMIO, or SerDes power cycling.
set -eu
export PATH=/usr/sbin:/usr/bin:/sbin:/bin
for count in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20; do
    if [ -d /sys/class/net/eth1 ] && [ -d /sys/class/net/lan2 ]; then
        break
    fi
    sleep 1
done
[ -d /sys/class/net/eth1 ] || {
    echo PUBLIC_MT6990_NETSYS_ETH1_ABSENT >&2
    exit 1
}
[ -d /sys/class/net/lan2 ] || {
    echo PUBLIC_MT7531_DSA_LAN2_ABSENT >&2
    exit 1
}
# Only standard netlink is used here; the driver owns PCS, PHY and DMA.
ip link set eth1 up
ip link set lan2 up
# Let the P44-owned networkd configuration assign addresses. Do not
# invent a hard-coded IP, route, login or per-device identity here.
echo PUBLIC_MT6990_NETSYS_DSA_LINKS_REGISTERED
echo PUBLIC_MANAGEMENT_EXPECTS_P44_NETWORKD_AND_SSH
