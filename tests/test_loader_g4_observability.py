#!/usr/bin/env python3
"""G4 UART observational contract. Host-only; never accesses a device."""
from pathlib import Path
import subprocess
import unittest

SRC = Path(__file__).resolve().parents[1] / "initramfs" / "loader-init"

class TestG4Observability(unittest.TestCase):
    def test_shell_parses(self):
        subprocess.run(["sh", "-n", str(SRC)], check=True)

    def test_diagnostic_bounds_and_stage_markers(self):
        s = SRC.read_text()
        self.assertIn('while [ "$i" -lt 5 ]', s)
        for marker in ("LAN2_CARRIER", "LAN2_ADDRESS_MISSING",
                       "LAN2_LINK_SET_FAILED", "LAN2_ADDRESS_ADD_FAILED",
                       "LAN2_rx_packets", "LAN2_tx_packets", "LAN2_SSH_FAILED"):
            # Counters are emitted from a loop, while error markers are literal.
            if marker.endswith(("rx_packets", "tx_packets")):
                self.assertIn('for counter in rx_packets tx_packets', s)
            elif marker == "LAN2_SSH_FAILED":
                self.assertIn("TERMINAL6_LOADER_SSH_FAILED", s)
            else:
                self.assertIn("TERMINAL6_LOADER_" + marker, s)
        self.assertIn('elif dropbear -E -s -r "$SSHKEY"', s)
        self.assertIn("TERMINAL6_LOADER_SSH_BLOCKED_NO_P26_UART_ONLY", s)
        self.assertIn("TERMINAL6_LOADER_SSH_BLOCKED_NO_AUTHORIZED_KEYS_UART_ONLY", s)
        self.assertNotIn("dropbear -E -B", s)
        self.assertNotIn("ip -d link", s)
        self.assertIn("ip link show dev lan2", s)
        self.assertNotIn('dropbear -E -B -r "$SSHKEY" -p "$IP:22" || echo', s)

if __name__ == "__main__":
    unittest.main()
