#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
import importlib.util
import sys
import unittest

spec = importlib.util.spec_from_file_location("guard", sys.argv.pop(1))
guard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(guard)


class Topology(unittest.TestCase):
    def setUp(self):
        self.links = [
            {"ifname": "br-lan", "linkinfo": {"info_kind": "bridge"}},
            {"ifname": "lan2", "master": "br-lan", "flags": ["UP", "LOWER_UP"]},
            {"ifname": "lan3", "master": "br-lan", "flags": ["UP"]},
        ]
        self.addrs = [{"ifname": "br-lan", "addr_info": [
            {"family": "inet", "local": "192.168.1.1", "prefixlen": 24},
        ]}]
        self.routes = [{"dev": "br-lan", "prefsrc": "192.168.1.1"}]

    def check(self, port="lan2"):
        guard.verify_topology(port, self.links, self.addrs, self.routes)

    def test_either_direct_port(self):
        self.check()
        self.links[1]["flags"].remove("LOWER_UP")
        self.links[2]["flags"].append("LOWER_UP")
        self.check("lan3")

    def test_other_connected_port(self):
        self.links[2]["flags"].append("LOWER_UP")
        with self.assertRaisesRegex(ValueError, "carrier"):
            self.check()

    def test_no_carrier(self):
        self.links[1]["flags"].remove("LOWER_UP")
        with self.assertRaisesRegex(ValueError, "carrier"):
            self.check()

    def test_unexpected_member(self):
        self.links.append({"ifname": "wlan0", "master": "br-lan"})
        with self.assertRaisesRegex(ValueError, "membership"):
            self.check()

    def test_duplicate_management_address(self):
        self.addrs.append({"ifname": "eth0", "addr_info": self.addrs[0]["addr_info"]})
        with self.assertRaisesRegex(ValueError, "owner"):
            self.check()

    def test_routed_peer(self):
        self.routes[0]["gateway"] = "192.168.1.254"
        with self.assertRaisesRegex(ValueError, "bridge route"):
            self.check()


if __name__ == "__main__":
    unittest.main()
