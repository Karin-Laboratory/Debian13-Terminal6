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


LEAN_REQUIRED = (
    "CONFIG_ARM64_4K_PAGES", "CONFIG_ARM64_VA_BITS_39",
    "CONFIG_COMMON_CLK_MT6990", "CONFIG_COMMON_CLK_MT6990_PERI",
    "CONFIG_PHY_MTK_MT6990_SGMII", "CONFIG_PHYLINK",
    "CONFIG_MFD_SYSCON", "CONFIG_PINCTRL_MTK", "CONFIG_REGULATOR",
    "CONFIG_GPIOLIB", "CONFIG_PM", "CONFIG_FHANDLE",
    "CONFIG_SECCOMP", "CONFIG_SECCOMP_FILTER",
    "CONFIG_UTS_NS", "CONFIG_IPC_NS", "CONFIG_PID_NS", "CONFIG_NET_NS",
    "CONFIG_MODULES", "CONFIG_MODULE_UNLOAD",
)
LEAN_MODULES = (
    "CONFIG_OVERLAY_FS", "CONFIG_TUN", "CONFIG_VETH", "CONFIG_BLK_DEV_LOOP",
)


def lean_problems(text):
    options = dict(line.split("=", 1) for line in text.splitlines()
                   if line.startswith("CONFIG_") and "=" in line)
    failures = [x for x in LEAN_REQUIRED if options.get(x) != "y"]
    failures += [f"{x}=m" for x in LEAN_MODULES if options.get(x) != "m"]
    if options.get("CONFIG_ARM64_VA_BITS") != "39":
        failures.append("CONFIG_ARM64_VA_BITS=39")
    return failures


def missing(text, board=False):
    options = dict(line.split("=", 1) for line in text.splitlines()
                   if line.startswith("CONFIG_") and "=" in line)
    return [key for key in REQUIRED + (BOARD_REQUIRED if board else ())
            if options.get(key) != "y"]

if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("config", type=Path)
    p.add_argument("--terminal6", action="store_true")
    p.add_argument("--lean", action="store_true")
    a = p.parse_args()
    if a.lean and not a.terminal6:
        p.error("--lean requires --terminal6")
    cfg = a.config.read_text()
    absent = missing(cfg, a.terminal6)
    if a.lean:
        absent += lean_problems(cfg)
    if absent:
        raise SystemExit("KCONFIG_FAIL: " + ", ".join(absent))
    print("DEBIAN_T6_REQUIRED_KCONFIG_PASS")
    if a.lean:
        print("DEBIAN_T6_LEAN_BUILTIN_AND_MODULE_CONFIG_PASS")
    print("Kconfig presence does not prove DT-compatible driver bindings or physical boot")
