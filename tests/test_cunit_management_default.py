#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""C-unit owner-personalized first-boot management IPv4 contract."""
import ipaddress
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class InitialManagementIpTest(unittest.TestCase):
    def test_openwrt_familiar_default(self):
        cidr = (ROOT / "configs/cunit-initial-management.cidr").read_text().strip()
        interface = ipaddress.ip_interface(cidr)
        self.assertEqual(str(interface), "192.168.1.1/24")

    def test_shared_private_stage_and_initramfs_rescue(self):
        stage = (ROOT / "scripts/stage-rescue-ssh.sh").read_text()
        rescue = (ROOT / "scripts/initramfs-rescue.sh").read_text()
        self.assertIn("configs/cunit-initial-management.cidr", stage)
        self.assertIn("etc/dropbear/management-ip", stage)
        self.assertIn("rescue_ip=192.168.1.1", rescue)
        self.assertIn("rescue_prefix=24", rescue)
        self.assertIn("ISOLATED_MANAGEMENT_ONLY", rescue)

    def test_p44_runtime_static_ip_only_when_isolated(self):
        init = (ROOT / "initramfs/init").read_text()
        self.assertIn("/terminal6-rescue-root/etc/dropbear/ISOLATED_MANAGEMENT_ONLY", init)
        self.assertIn("initial_cidr=192.168.1.1/24", init)
        self.assertIn("10-cunit-isolated-management.network", init)
        self.assertIn("Address=$initial_cidr", init)
        self.assertIn("DHCP=no", init)
        self.assertIn("Name=lan2", init)
        self.assertIn("/newroot/run/systemd/network/", init)
        self.assertNotIn("192.168.3.1/24", init)


if __name__ == "__main__":
    unittest.main()
