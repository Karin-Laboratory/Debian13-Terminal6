#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Verify directly-mounted ext4, mmc, serial and systemd-required options."""
from pathlib import Path
import sys

REQUIRED = (
    "CONFIG_DEVTMPFS", "CONFIG_DEVTMPFS_MOUNT", "CONFIG_EXT4_FS",
    "CONFIG_MMC", "CONFIG_MMC_BLOCK", "CONFIG_SERIAL_8250",
    "CONFIG_SERIAL_8250_CONSOLE", "CONFIG_CGROUPS", "CONFIG_NAMESPACES",
    "CONFIG_TMPFS", "CONFIG_UNIX", "CONFIG_INET", "CONFIG_NET",
)

def missing(text):
    options = dict(line.split("=", 1) for line in text.splitlines()
                   if line.startswith("CONFIG_") and "=" in line)
    return [key for key in REQUIRED if options.get(key) != "y"]

if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("usage: verify-kconfig.py .config")
    absent = missing(Path(sys.argv[1]).read_text())
    if absent:
        sys.exit("KCONFIG_FAIL: " + ", ".join(absent))
    print("DEBIAN_T6_REQUIRED_KCONFIG_PASS")
