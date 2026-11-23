"""C4 G4 bounded tracefs rescue diagnostic policy and BusyBox contract."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]

class TestG4Trace(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.t = (ROOT / "initramfs/terminal6-g4-trace").read_text()

    def test_bounded_trace_events(self):
        for event in ("net_dev_queue", "net_dev_start_xmit", "net_dev_xmit", "netif_receive_skb", "kfree_skb"):
            self.assertIn(event, self.t)
        self.assertIn("buffer_size_kb", self.t)
        self.assertIn("sleep 15", self.t)
        self.assertIn("tail -n 120", self.t)
        self.assertIn("trap cleanup EXIT HUP INT TERM", self.t)

    def test_readonly_device_policy(self):
        for forbidden in ("dd if=", "dd of=", "flash_erase", "sgdisk", "parted", "fw_setenv", "mmc bootpart", "reboot", "ip link set", "tc qdisc"):
            self.assertNotIn(forbidden, self.t)
        self.assertIn("TERMINAL6_G4_TRACEFS_UNAVAILABLE", self.t)
        self.assertIn("TERMINAL6_G4_TRACE_NO_NET_EVENTS", self.t)
        self.assertIn("TERMINAL6_G4_TRACE_V1_END", self.t)
