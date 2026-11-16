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
    "CONFIG_ARM64_4K_PAGES", "CONFIG_PAGE_SIZE_4KB", "CONFIG_ARM64_VA_BITS_39",
    "CONFIG_COMMON_CLK_MT6990", "CONFIG_COMMON_CLK_MT6990_PERI",
    "CONFIG_PHY_MTK_MT6990_SGMII", "CONFIG_PHYLINK",
    "CONFIG_MFD_SYSCON", "CONFIG_PINCTRL_MTK", "CONFIG_REGULATOR",
    "CONFIG_GPIOLIB", "CONFIG_PM", "CONFIG_FHANDLE",
    "CONFIG_SECCOMP", "CONFIG_SECCOMP_FILTER",
    "CONFIG_UTS_NS", "CONFIG_IPC_NS", "CONFIG_PID_NS", "CONFIG_NET_NS",
    "CONFIG_SYSVIPC", "CONFIG_MODULES", "CONFIG_MODULE_UNLOAD",
)
LEAN_MODULES = (
    "CONFIG_OVERLAY_FS", "CONFIG_TUN", "CONFIG_VETH", "CONFIG_BLK_DEV_LOOP",
)


# Extended source-only profile. These gates are build contracts, not proof of
# MT7990 firmware calibration, physical PCIe/USB, C-unit LK or P44 boot.
FULL35_BUILTINS = (
    "CONFIG_VIRTUALIZATION", "CONFIG_KVM", "CONFIG_PCI",
    "CONFIG_PCIE_MEDIATEK_GEN3", "CONFIG_USB_SUPPORT", "CONFIG_USB",
    "CONFIG_WIRELESS", "CONFIG_WLAN", "CONFIG_FW_LOADER",
)
FULL35_MODULES = (
    "CONFIG_CFG80211", "CONFIG_MAC80211", "CONFIG_MT76",
    "CONFIG_MT76_CONNAC_LIB", "CONFIG_MT7996E",
    "CONFIG_USB_XHCI_HCD", "CONFIG_USB_XHCI_PLATFORM",
    "CONFIG_USB_SERIAL", "CONFIG_USB_SERIAL_CH341",
)


def full35_problems(text):
    options = dict(line.split("=", 1) for line in text.splitlines()
                   if line.startswith("CONFIG_") and "=" in line)
    failures = lean_problems(text)
    failures += [key for key in FULL35_BUILTINS if options.get(key) != "y"]
    failures += [f"{key}=m" for key in FULL35_MODULES if options.get(key) != "m"]
    return failures


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
    p.add_argument("--full35", action="store_true")
    a = p.parse_args()
    if (a.lean or a.full35) and not a.terminal6:
        p.error("--lean/--full35 require --terminal6")
    if a.lean and a.full35:
        p.error("--lean and --full35 are mutually exclusive")
    cfg = a.config.read_text()
    absent = missing(cfg, a.terminal6)
    if a.lean:
        absent += lean_problems(cfg)
    if a.full35:
        absent += full35_problems(cfg)
    if absent:
        if a.lean or a.full35:
            # Fail-closed troubleshooting without exposing kernel binaries,
            # serial identifiers, credentials or private build inputs.
            keys = ("ARM64_VA_BITS", "ARM64_VA_BITS_39", "ARM64_VA_BITS_48",
                    "ARM64_VA_BITS_52", "PAGE_SIZE_4KB", "ARM64_4K_PAGES")
            values = dict(line.split("=", 1) for line in cfg.splitlines()
                          if line.startswith("CONFIG_") and "=" in line)
            print("LEAN_KCONFIG_SELECTED_CHOICES " +
                  " ".join(f"CONFIG_{key}={values.get('CONFIG_' + key, 'n')}"
                           for key in keys))
        raise SystemExit("KCONFIG_FAIL: " + ", ".join(absent))
    print("DEBIAN_T6_REQUIRED_KCONFIG_PASS")
    if a.lean:
        print("DEBIAN_T6_LEAN_BUILTIN_AND_MODULE_CONFIG_PASS")
    if a.full35:
        print("DEBIAN_T6_FULL35_KVM_PCIE_MT7990_USB_CONFIG_PASS_NOT_HARDWARE_VALIDATED")
    print("Kconfig presence does not prove DT-compatible driver bindings or physical boot")
