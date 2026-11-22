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
        self.assertIn('dropbear -E -s -r "$SSHKEY" -p "$IP:22"', data)
        self.assertIn("TERMINAL6_LOADER_SSH_BLOCKED_NO_P26_UART_ONLY", data)
        self.assertIn("TERMINAL6_LOADER_SSH_BLOCKED_NO_AUTHORIZED_KEYS_UART_ONLY", data)
        self.assertNotIn("dropbear -E -B", data)
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
        self.assertIn("--enable KEXEC", s)
        self.assertIn("--enable SUSPEND", s)
        self.assertIn("--disable PCI", s)
        self.assertIn("--disable WIRELESS", s)
        self.assertIn("--disable USB_SUPPORT", s)
        self.assertIn("LOCALVERSION", s)

    def test_real_util_linux_commands_not_broken_busybox_links(self):
        s = (ROOT / "scripts/build-loader-initramfs.sh").read_text()
        self.assertIn("kexec blkid mountpoint", s)
        self.assertIn('test ! -L "$tmp/sbin/$tool"', s)
        self.assertNotIn("umount mountpoint blkid cat", s)
        self.assertIn("INITRAMFS_REQUIRED_BUSYBOX_APPLET_MISSING", s)

    def test_real_arm64_command_execution_in_ci(self):
        s = (ROOT / "tests/smoke-loader-initramfs.sh").read_text()
        self.assertIn("sudo chroot", s)
        self.assertIn("P26_EXT4_PROBE_FAIL", s)
        self.assertIn("P26_SQUASHFS_PROBE_FAIL", s)
        self.assertIn("P26_CORRUPTION_FALSE_EXT4", s)
        self.assertIn("P26_MISSING_FALSE_FS", s)
        self.assertIn("UNMOUNTED_P43_FALSE_POSITIVE", s)

    def test_packager_profile_independent_of_p44(self):
        import json
        p = json.loads((ROOT / "configs/minimal-loader-boot-v2-profile.json").read_text())
        self.assertIn("t6_loader=1", p["cmdline"])
        self.assertIn("rdinit=/init", p["cmdline"])
        self.assertIn("console=ttyS0,115200n8", p["cmdline"])
        self.assertNotIn("console=ttyS0,115200n1", p["cmdline"])
        self.assertNotIn("rootfs_data", p["cmdline"])


if __name__ == "__main__":
    unittest.main()
