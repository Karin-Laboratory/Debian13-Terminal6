#!/bin/sh
# SPDX-License-Identifier: MIT
# Read-only C-unit public P25 acceptance probe. Run on C unit from console/SSH.
# Never flashes, changes slots, brings links up, or prints credentials.
set -eu
export PATH=/usr/sbin:/usr/bin:/sbin:/bin
pass=0
fail=0
ok() { printf 'PASS %s\n' "$1"; pass=$((pass+1)); }
bad() { printf 'FAIL %s\n' "$1"; fail=$((fail+1)); }
check_file() {
    if [ -r "$1" ]; then ok "$2"; else bad "$2"; fi
}
printf 'PUBLIC_P25_CUNIT_READONLY_ACCEPTANCE_V1\n'
printf 'KERNEL='
uname -r
case "$(uname -r)" in
    6.18.63*) ok KERNEL_6_18_63 ;;
    *) bad KERNEL_6_18_63 ;;
esac
if grep -q 'rootfs_data' /proc/cmdline; then
    ok CMDLINE_ROOTFS_DATA
else
    bad CMDLINE_ROOTFS_DATA
fi
root_src=$(findmnt -n -o SOURCE / 2>/dev/null || :)
root_fstype=$(findmnt -n -o FSTYPE / 2>/dev/null || :)
printf 'ROOT_SOURCE=%s ROOT_TYPE=%s\n' "$root_src" "$root_fstype"
if [ "$root_fstype" = ext4 ]; then ok P44_EXT4_ROOT; else bad P44_EXT4_ROOT; fi
root_partlabel=$(blkid -s PARTLABEL -o value "$root_src" 2>/dev/null || :)
if [ "$root_partlabel" = rootfs_data ]; then
    ok ROOT_PARTLABEL_ROOTFS_DATA
else
    bad ROOT_PARTLABEL_ROOTFS_DATA
fi
for name in eth1 lan2; do
    if [ -e "/sys/class/net/$name" ]; then
        ok "NETDEV_$name"
        if [ -r "/sys/class/net/$name/carrier" ]; then
            printf 'CARRIER_%s=%s\n' "$name" "$(cat "/sys/class/net/$name/carrier")"
        fi
    else
        bad "NETDEV_$name"
    fi
done
if [ -e /sys/class/net/lan2 ] && [ "$(cat /sys/class/net/lan2/carrier 2>/dev/null || :)" = 1 ]; then
    ok LAN2_PHYSICAL_CARRIER
else
    bad LAN2_PHYSICAL_CARRIER
fi
if [ -e /sys/class/net/lan2 ]; then
    printf 'LAN2_SPEED=%s\n' "$(cat /sys/class/net/lan2/speed 2>/dev/null || :)"
    printf 'LAN2_DUPLEX=%s\n' "$(cat /sys/class/net/lan2/duplex 2>/dev/null || :)"
fi
if systemctl -q is-active systemd-networkd 2>/dev/null; then
    ok NETWORKD_ACTIVE
else
    bad NETWORKD_ACTIVE
fi
if systemctl -q is-active ssh 2>/dev/null; then
    ok SSH_SERVICE_ACTIVE
else
    bad SSH_SERVICE_ACTIVE
fi
if command -v ss >/dev/null 2>&1 &&
    ss -lnt | grep -Eq ':[0-9]*22[[:space:]]'; then
    ok SSH_LISTENING
else
    bad SSH_LISTENING
fi
# Do not dump dmesg, boot partitions, serial numbers, MACs, SSH keys or
# individual calibration to logs. Independent raspi4 -> C SSH and UART
# cold boot evidence must be collected by an authorized operator.
printf 'SUMMARY PASS=%d FAIL=%d\n' "$pass" "$fail"
if [ "$fail" -ne 0 ]; then exit 1; fi
printf 'DEVICE_LOCAL_CHECKS_PASS_NOT_PROOF_OF_PUBLIC_BUILD_PROVENANCE_OR_COLD_BOOT\n'
