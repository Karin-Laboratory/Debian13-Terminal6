#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Check boot observability, Debian execution, and optional board driver closure."""
from pathlib import Path
import argparse

REQUIRED = (
    "CONFIG_PRINTK", "CONFIG_PRINTK_TIME", "CONFIG_BINFMT_ELF",
    "CONFIG_BINFMT_SCRIPT", "CONFIG_ARM_GIC", "CONFIG_ARM_GIC_V3",
    "CONFIG_ARM_ARCH_TIMER", "CONFIG_SERIAL_EARLYCON",
    "CONFIG_SERIAL_8250", "CONFIG_SERIAL_8250_CONSOLE",
    "CONFIG_SERIAL_8250_MT6577", "CONFIG_DEVTMPFS", "CONFIG_DEVTMPFS_MOUNT",
    "CONFIG_BLK_DEV_INITRD", "CONFIG_RD_GZIP", "CONFIG_EXT4_FS",
    "CONFIG_EFI_PARTITION", "CONFIG_MMC", "CONFIG_MMC_BLOCK", "CONFIG_MMC_MTK",
    "CONFIG_PROC_FS", "CONFIG_SYSFS", "CONFIG_TMPFS", "CONFIG_CGROUPS",
    "CONFIG_NAMESPACES", "CONFIG_FUTEX", "CONFIG_EPOLL", "CONFIG_SIGNALFD",
    "CONFIG_TIMERFD", "CONFIG_INOTIFY_USER", "CONFIG_UNIX", "CONFIG_INET", "CONFIG_NET",
    "CONFIG_IKCONFIG", "CONFIG_IKCONFIG_PROC",
)
BOARD_REQUIRED = (
    "CONFIG_ARCH_MEDIATEK", "CONFIG_NET_VENDOR_MEDIATEK", "CONFIG_NET_MEDIATEK_SOC",
    "CONFIG_NET_DSA", "CONFIG_NET_DSA_MT7530", "CONFIG_NET_DSA_MT7530_MDIO",
    "CONFIG_PCS_MTK_LYNXI", "CONFIG_BRIDGE",
)

def missing(text, board=False):
    options = dict(line.split("=", 1) for line in text.splitlines()
                   if line.startswith("CONFIG_") and "=" in line)
    return [key for key in REQUIRED + (BOARD_REQUIRED if board else ())
            if options.get(key) != "y"]

if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("config", type=Path)
    p.add_argument("--terminal6", action="store_true")
    a = p.parse_args()
    absent = missing(a.config.read_text(), a.terminal6)
    if absent:
        raise SystemExit("KCONFIG_FAIL: " + ", ".join(absent))
    print("DEBIAN_T6_REQUIRED_KCONFIG_PASS")
    print("Kconfig presence does not prove DT-compatible driver bindings or physical boot")
