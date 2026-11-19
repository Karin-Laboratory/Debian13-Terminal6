#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Fail-closed resolved-Kconfig contract for public C-unit capable profile.

A source-build contract is not evidence of live hardware/firmware support.
"""
from pathlib import Path
import argparse
import importlib.util

ROOT = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("lean_contract", ROOT / "verify-kconfig.py")
assert spec is not None and spec.loader is not None
lean = importlib.util.module_from_spec(spec)
spec.loader.exec_module(lean)

BUILTINS = (
    "VIRTUALIZATION", "KVM", "PCI", "PCI_MSI",
    "PCIE_MEDIATEK_GEN3", "PHY_MTK_PCIE", "WIRELESS", "WLAN",
    "USB_SUPPORT", "USB",
)
MODULES = (
    "CFG80211", "MAC80211", "MT7996E",
    "USB_XHCI_HCD", "USB_XHCI_MTK", "PHY_MTK_TPHY",
    "USB_SERIAL", "USB_SERIAL_CH341",
    "SCSI", "BLK_DEV_SD", "USB_STORAGE",
)
EARLY_BOOT_BUILTINS = ("RELOCATABLE", "RANDOMIZE_BASE", "SERIAL_OF_PLATFORM")
EXPECTED_NR_CPUS = "4"
EXPECTED_MMC_BLOCK_MINORS = "64"
EXPECTED_LOCALVERSION = '"-t6-public-capable"'
MAX_IMAGE_BYTES = 35 * 1024 * 1024
P25_BYTES = 32 * 1024 * 1024


def problems(text: str) -> list[str]:
    options = dict(line.split("=", 1) for line in text.splitlines()
                   if line.startswith("CONFIG_") and "=" in line)
    errors = lean.missing(text, board=True) + lean.lean_problems(text)
    errors += [f"CONFIG_{key}=y" for key in BUILTINS if options.get("CONFIG_" + key) != "y"]
    errors += [f"CONFIG_{key}=m" for key in MODULES if options.get("CONFIG_" + key) != "m"]
    errors += [f"CONFIG_{key}=y" for key in EARLY_BOOT_BUILTINS
               if options.get("CONFIG_" + key) != "y"]
    if options.get("CONFIG_MMC_BLOCK_MINORS") != EXPECTED_MMC_BLOCK_MINORS:
        errors.append("CONFIG_MMC_BLOCK_MINORS=64")
    if options.get("CONFIG_REGULATOR_FIXED_VOLTAGE") != "y":
        errors.append("CONFIG_REGULATOR_FIXED_VOLTAGE=y")
    if options.get("CONFIG_NR_CPUS") != EXPECTED_NR_CPUS:
        errors.append("CONFIG_NR_CPUS=4")
    if options.get("CONFIG_LOCALVERSION") != EXPECTED_LOCALVERSION:
        errors.append("CONFIG_LOCALVERSION=-t6-public-capable")
    if options.get("CONFIG_LOCALVERSION_AUTO") == "y":
        errors.append("CONFIG_LOCALVERSION_AUTO=n")
    return errors


def check(config: Path, image: Path | None = None) -> None:
    errors = problems(config.read_text(encoding="utf-8"))
    if errors:
        raise SystemExit("TERMINAL6_CAPABLE_KCONFIG_FAIL: " + ", ".join(errors))
    if image:
        size = image.stat().st_size
        if not 0 < size <= MAX_IMAGE_BYTES:
            raise SystemExit(f"TERMINAL6_CAPABLE_IMAGE_SIZE_FAIL {size} > {MAX_IMAGE_BYTES}")
        raw = image.open("rb")
        with raw:
            raw.seek(56)
            if raw.read(4) != b"ARM\x64":
                raise SystemExit("TERMINAL6_CAPABLE_IMAGE_AARCH64_MAGIC_FAIL")
        print(f"TERMINAL6_CAPABLE_IMAGE_35M_PASS {size}")
    print("TERMINAL6_CAPABLE_CONFIG_CONTRACT_PASS_KVM_PCIE_MT7996_USB_P44")
    print("HARDWARE_DTB_CALIBRATION_RF_AND_P44_MODULE_DEPLOYMENT_NOT_TESTED")


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("config", type=Path)
    p.add_argument("--image", type=Path)
    a = p.parse_args()
    check(a.config, a.image)


if __name__ == "__main__":
    main()
