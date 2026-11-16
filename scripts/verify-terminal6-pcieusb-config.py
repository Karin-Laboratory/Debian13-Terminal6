#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Fail-closed MT6990 PCIe/USB feature and distinct module ABI contract."""
from pathlib import Path
import argparse
import importlib.util

ROOT = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("public_capable", ROOT / "verify-terminal6-capable-config.py")
assert spec and spec.loader
capable = importlib.util.module_from_spec(spec)
spec.loader.exec_module(capable)

PCIEUSB_MODULES = ("USB_MTU3", "PHY_MTK_XSPHY")
PCIEUSB_BUILTINS = ("USB_MTU3_HOST",)
EXPECTED_LOCALVERSION = '"-t6-public-pcieusb"'
EXPECTED_RELEASE = "6.18.63-t6-public-pcieusb"

def problems(text: str) -> list[str]:
    options = dict(line.split("=", 1) for line in text.splitlines()
                   if line.startswith("CONFIG_") and "=" in line)
    errors = capable.problems(text.replace("CONFIG_LOCALVERSION=" + EXPECTED_LOCALVERSION,
                                           "CONFIG_LOCALVERSION=" + capable.EXPECTED_LOCALVERSION))
    errors += [f"CONFIG_{name}=m" for name in PCIEUSB_MODULES
               if options.get("CONFIG_" + name) != "m"]
    errors += [f"CONFIG_{name}=y" for name in PCIEUSB_BUILTINS
               if options.get("CONFIG_" + name) != "y"]
    if options.get("CONFIG_LOCALVERSION") != EXPECTED_LOCALVERSION:
        errors.append("CONFIG_LOCALVERSION=" + EXPECTED_LOCALVERSION)
    return errors

def check(path: Path, image: Path | None = None) -> None:
    errors = problems(path.read_text(encoding="utf-8"))
    if errors:
        raise SystemExit("CUNIT_PCIEUSB_CONFIG_FAIL: " + ", ".join(errors))
    if image:
        with image.open("rb") as fd:
            fd.seek(56)
            if fd.read(4) != b"ARM\x64":
                raise SystemExit("CUNIT_PCIEUSB_ARM64_IMAGE_MAGIC_FAIL")
        size = image.stat().st_size
        if not 0 < size <= capable.MAX_IMAGE_BYTES:
            raise SystemExit(f"CUNIT_PCIEUSB_35M_IMAGE_FAIL: {size}")
        print(f"CUNIT_PCIEUSB_35M_IMAGE_PASS bytes={size}")
    print("CUNIT_PCIEUSB_PCI_MT6990_USB_MTU3_HOST_XSPHY_CONFIG_PASS")
    print("HARDWARE_LINK_USB_VBUS_LK_BOOT_NOT_TESTED")

if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("config", type=Path)
    p.add_argument("--image", type=Path)
    a = p.parse_args()
    check(a.config, a.image)
