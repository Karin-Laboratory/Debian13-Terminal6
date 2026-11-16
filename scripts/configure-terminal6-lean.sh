#!/usr/bin/env bash
# SPDX-License-Identifier: MIT
# Executed IN the pinned Linux 6.18.63 build tree after tinyconfig.
# Fail-closed terminal6-lean engineering profile, NOT hardware acceptance.
set -euo pipefail
test -x scripts/config
test "$(make -s kernelversion)" = 6.18.63
# Keep boot memory layout aligned to the observed C-unit family, rather than
# accepting tinyconfig's default VA geometry.
scripts/config --enable ARM64 --enable ARM64_4K_PAGES --enable ARM64_VA_BITS_39 \
  --enable PAGE_SIZE_4KB --enable MMU --enable SMP --enable BLOCK --enable MULTIUSER \
  --enable TTY --enable SHMEM --enable OF --enable ARCH_MEDIATEK \
  --enable COMMON_CLK --enable COMMON_CLK_MEDIATEK \
  --enable COMMON_CLK_MT6990 --enable COMMON_CLK_MT6990_PERI \
  --enable MFD_SYSCON --enable REGMAP --enable SOC_BUS \
  --enable PINCTRL --enable PINCTRL_MTK --enable REGULATOR \
  --enable GPIOLIB --enable GENERIC_PHY --enable PHY_MTK_MT6990_SGMII \
  --enable PM --enable MODULES --enable MODULE_UNLOAD
# ARM64 VA width is a Kconfig 'choice' with a 52-bit default. Disable all
# other choices explicitly, including any carried forward by tinyconfig.
scripts/config --disable ARM64_VA_BITS_52 --disable ARM64_VA_BITS_48 \
  --disable ARM64_VA_BITS_47 --disable ARM64_VA_BITS_42 \
  --disable ARM64_VA_BITS_36 --enable ARM64_VA_BITS_39
# First-boot requirements must not depend on a P44 module loader.
scripts/config --enable PRINTK --enable PRINTK_TIME \
  --enable BINFMT_ELF --enable BINFMT_SCRIPT \
  --enable ARM_GIC --enable ARM_GIC_V3 --enable ARM_ARCH_TIMER \
  --enable SERIAL_EARLYCON --enable SERIAL_8250 --enable SERIAL_8250_CONSOLE \
  --enable SERIAL_8250_MT6577 --enable DEVTMPFS --enable DEVTMPFS_MOUNT \
  --enable BLK_DEV_INITRD --enable RD_GZIP --enable EFI_PARTITION \
  --enable MMC --enable MMC_BLOCK --enable MMC_MTK --enable EXT4_FS \
  --enable PROC_FS --enable SYSFS --enable TMPFS
# Debian systemd, SSH and network runtime. Keep the independent required
# Kconfig verifier from the public project; do not weaken it.
scripts/config --enable FUTEX --enable EPOLL --enable SIGNALFD \
  --enable TIMERFD --enable INOTIFY_USER --enable UNIX \
  --enable INET --enable NET --enable CGROUPS \
  --enable SYSVIPC --enable NAMESPACES --enable UTS_NS --enable IPC_NS \
  --enable PID_NS --enable NET_NS --enable FHANDLE \
  --enable TMPFS_POSIX_ACL --enable EXT4_FS_POSIX_ACL \
  --enable SECCOMP --enable SECCOMP_FILTER \
  --enable IKCONFIG --enable IKCONFIG_PROC
# The public upstream Linux 6.18 network source replay already builds these
# as builtins. Forbid modular DSA/SoC LAN until the P44 handoff is complete.
scripts/config --disable HSR --enable IPV6 \
  --enable NETDEVICES --enable ETHERNET --enable BRIDGE \
  --enable NET_DSA --enable NET_VENDOR_MEDIATEK \
  --enable NET_MEDIATEK_SOC --enable NET_DSA_MT7530 \
  --enable NET_DSA_MT7530_MDIO --enable PHYLINK \
  --enable PCS_MTK_LYNXI
# Reduce Image's *uncompressed* size; avoid bundled drivers for unrelated
# SoCs. No ability check is skipped, and the 35MiB protected signer is
# completely unaffected.
scripts/config --enable CC_OPTIMIZE_FOR_SIZE \
  --disable DEBUG_INFO --disable DEBUG_INFO_BTF \
  --disable DRM --disable SOUND --disable SCSI \
  --disable MEDIA_SUPPORT --disable HWMON \
  --disable WIRELESS --disable WLAN \
  --disable USB --disable USB_SUPPORT \
  --disable NFS_FS --disable NFS_V4 \
  --disable VIRTUALIZATION
# A few useful post-P44 services can be modules, preserving the build identity.
# Do not declare deployment complete until same-build modules are installed.
scripts/config --module OVERLAY_FS --module TUN --module VETH \
  --module BLK_DEV_LOOP
echo "TERMINAL6_LEAN_KCONFIG_REQUESTED_NOT_YET_RESOLVED"
