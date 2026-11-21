#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Offline structural safety checks for the experimental minimal signed-P25 source."""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]


class LoaderSourceTests(unittest.TestCase):
    def test_p25_init_independent_of_p44(self):
        data = (ROOT / "initramfs/loader-init").read_text()
        self.assertIn("TERMINAL6_LOADER_INIT_STARTED", data)
        self.assertNotIn("DEBIAN13_T6_SWITCH_ROOT_P44", data)
        self.assertIn("PARTNAME=$wanted", data)
        self.assertIn("P26_UNAVAILABLE_RAM_RESCUE", data)
        self.assertIn('dropbear -E -B -r "$SSHKEY" -p "$IP:22"', data)
        self.assertNotIn("0.0.0.0:22", data)

    def test_boot_manager_gate_and_one_shot(self):
        s = (ROOT / "initramfs/terminal6-boot").read_text()
        self.assertIn("mountpoint -q /userdata", s)
        self.assertIn("TERMINAL6_LOADER_KEXEC_START_OS", s)
        self.assertIn("sed -i 's/^next=.*/next=/'", s)
        self.assertLess(s.index("NEXT_CLEAR_FAILED"), s.index("kexec -e"))
        self.assertIn("mount -o remount,ro /config", s)

    def test_kernel_profile_essential_and_exclusions(self):
        s = (ROOT / "scripts/configure-terminal6-lean.sh").read_text()
        self.assertIn("scripts/config --enable KEXEC", s)
        self.assertIn("--disable PCI", s)
        self.assertIn("--disable WIRELESS", s)
        self.assertIn("--disable USB_SUPPORT", s)
        self.assertIn("LOCALVERSION", s)

    def test_packager_profile_independent_of_p44(self):
        import json
        p = json.loads((ROOT / "configs/minimal-loader-boot-v2-profile.json").read_text())
        self.assertIn("t6_loader=1", p["cmdline"])
        self.assertIn("rdinit=/init", p["cmdline"])
        self.assertNotIn("rootfs_data", p["cmdline"])


if __name__ == "__main__":
    unittest.main()
