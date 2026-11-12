#!/usr/bin/env bash
# SPDX-License-Identifier: MIT
# Run inside a retained MT6990 source tree already upgraded to Linux 6.18.63.
set -euo pipefail
[[ $# -eq 2 ]] || { echo 'usage: configure-board-kernel.sh BASELINE_CONFIG INITRAMFS' >&2; exit 2; }
root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
test "$(make -s kernelversion)" = 6.18.63
test -s drivers/clk/mediatek/clk-mt6990.c
test -s drivers/phy/mediatek/phy-mtk-mt6990-sgmii.c
python3 "$root/scripts/port-mt6990-pll.py" "$PWD"
python3 "$root/scripts/repair-uart-stable-merge.py" "$PWD"
cp "$1" .config
for option in PRINTK PRINTK_TIME BINFMT_ELF BINFMT_SCRIPT ARM_GIC ARM_GIC_V3 \
 ARM_ARCH_TIMER SERIAL_EARLYCON SERIAL_8250 SERIAL_8250_CONSOLE SERIAL_8250_MT6577 \
 DEVTMPFS DEVTMPFS_MOUNT BLK_DEV_INITRD RD_GZIP EXT4_FS EFI_PARTITION MMC MMC_BLOCK MMC_MTK \
 PROC_FS SYSFS TMPFS CGROUPS NAMESPACES FUTEX EPOLL SIGNALFD TIMERFD INOTIFY_USER \
 UNIX INET NET IKCONFIG IKCONFIG_PROC ARCH_MEDIATEK NET_VENDOR_MEDIATEK NET_MEDIATEK_SOC \
 NET_DSA NET_DSA_MT7530 NET_DSA_MT7530_MDIO PCS_MTK_LYNXI BRIDGE MODULES MODULE_UNLOAD \
 COMMON_CLK_MT6990; do scripts/config --enable "$option"; done
scripts/config --disable CMDLINE_FORCE --disable LOCALVERSION_AUTO --disable DEBUG_INFO_BTF \
 --set-str CMDLINE '' --set-str LOCALVERSION '-debian-t6-proto2' --set-str INITRAMFS_SOURCE "$2"
# MT7987 is a different SoC. Its donor-only clock driver still targets the
# older PLL registration API and is not a dependency of MT6990.
for option in $(sed -n 's/^config \(COMMON_CLK_MT7987[^ ]*\).*/\1/p' drivers/clk/mediatek/Kconfig); do
  scripts/config --disable "$option"
done
make ARCH=arm64 olddefconfig
python3 "$root/scripts/verify-kconfig.py" --terminal6 .config
grep -qx CONFIG_COMMON_CLK_MT6990=y .config
# Preserve the tested board's page-table geometry rather than tinyconfig defaults.
grep -qx CONFIG_ARM64_VA_BITS=39 .config
