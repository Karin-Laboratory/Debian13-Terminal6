#!/bin/sh
# SPDX-License-Identifier: MIT
# Same NETSYS -> DSA -> carrier -> gated SGMII1 order as the C-unit RC14 test.
set -eu
here=${0%/*}
cd "$here"
sha256sum -c MODULE-SHA256SUMS
[ ! -e /run/terminal6-management-attempted ] || exit 1
: > /run/terminal6-management-attempted
for name in eth1 lan2 lan3; do [ ! -e "/sys/class/net/$name" ] || exit 1; done
insmod ./test23_netsys_fixedlink.ko mac_id=1
insmod ./test23_mdio_switch.ko mac_id=1 cpu_port=5
insmod ./test24_path_probe.ko writes=N
ip link set eth1 up
ip link set lan2 up
n=0
while [ "$n" -lt 30 ]; do
    [ "$(cat /sys/class/net/lan2/carrier 2>/dev/null || :)" = 1 ] && break
    sleep 1
    n=$((n+1))
done
[ "$(cat /sys/class/net/lan2/carrier)" = 1 ]
[ "$(cat /sys/class/net/lan2/speed)" = 1000 ]
[ "$(cat /sys/class/net/lan2/duplex)" = full ]
probe=/sys/module/test24_path_probe/parameters
case "$(cat "$probe/writes")" in N|0) ;; *) exit 1;; esac
printf '3\n' > "$probe/space"
printf '0x20\n' > "$probe/reg"
before=$(cat "$probe/value")
echo "DEBIAN13_T6_SGMII1_BEFORE=$before"
if [ "$before" != 0x31120009 ]; then
    trap 'printf "N\n" > "$probe/writes"' EXIT
    trap 'exit 1' HUP INT TERM
    printf 'Y\n' > "$probe/writes"
    printf '1\n' > "$probe/phy_init"
    printf 'N\n' > "$probe/writes"
    trap - EXIT HUP INT TERM
fi
case "$(cat "$probe/writes")" in N|0) ;; *) exit 1;; esac
printf '3\n' > "$probe/space"
printf '0x20\n' > "$probe/reg"
[ "$(cat "$probe/value")" = 0x31120009 ]
echo DEBIAN13_T6_MANAGEMENT_HARDWARE_READY
# Debian systemd-networkd assigns the lan2 address from the P44 configuration.
