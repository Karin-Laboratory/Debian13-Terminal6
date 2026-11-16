"""Offline tests for the phase-4 AMPE on-wire and supervised-auto contracts."""
import struct
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from scripts.mesh_peer_capture_audit import audit, frames_from_pcap
from scripts.mesh_peer_autorejoin import supervise


def packet(src, fc, payload=b""):
    # minimal 24-byte management/data header + body
    head = bytearray(24)
    head[:2] = fc.to_bytes(2, "little")
    head[10:16] = bytes.fromhex(src.replace(":", ""))
    return bytes(head) + payload


def pcap(frames):
    result = bytearray(struct.pack("<IHHIIII", 0xA1B2C3D4, 2, 4, 0, 0,
                                   65535, 127))
    for frame in frames:
        wire = b"\x00\x00\x08\x00\x00\x00\x00\x00" + frame
        result += struct.pack("<IIII", 1, 0, len(wire), len(wire)) + wire
    return bytes(result)


def protected_mesh_frames(address):
    mic = b"\x8c\x10" + bytes(range(16)) + bytes(range(20, 80))
    return [
        packet(address, 0x00B0, b"\x03\x00\x01\x00"),
        packet(address, 0x00D0, b"\x0f\x01" + b"\x00" * 5 + mic),
        packet(address, 0x00D0, b"\x0f\x02" + b"\x00" * 5 + mic),
        packet(address, 0x4008, b"\x11\x22\x33\x44"),
    ]


class CaptureContract(unittest.TestCase):
    def test_sae_ampe_mic_and_protected_data_two_transmitters(self):
        frames = (protected_mesh_frames("42:00:00:00:00:01") +
                  protected_mesh_frames("42:00:00:00:00:02"))
        receipt = audit(pcap(frames))
        self.assertTrue(receipt["pass"])
        self.assertEqual(receipt["distinct_transmitters"]["ampe_confirm"], 2)

    def test_plaintext_data_never_counts_as_protected(self):
        frames = (protected_mesh_frames("42:00:00:00:00:01") +
                  protected_mesh_frames("42:00:00:00:00:02"))
        frames = [f[:1] + b"\x00" + f[2:] if f[0] == 0x08 else f
                  for f in frames]
        self.assertFalse(audit(pcap(frames))["pass"])

    def test_mic_without_saes_never_passes(self):
        frames = (protected_mesh_frames("42:00:00:00:00:01") +
                  protected_mesh_frames("42:00:00:00:00:02"))
        frames = [f for f in frames if f[0] != 0xb0]
        self.assertFalse(audit(pcap(frames))["pass"])

    def test_empty_truncated_capture_fails_closed(self):
        with self.assertRaises(ValueError):
            list(frames_from_pcap(b"garbage"))
        with self.assertRaises(ValueError):
            list(frames_from_pcap(pcap([packet("42:00:00:00:00:01",
                                               0x4008)])[:-2]))

    def test_single_transmitter_cannot_satisfy_two_peers(self):
        self.assertFalse(audit(pcap(
            protected_mesh_frames("42:00:00:00:00:01")))["pass"])


class SupervisorContract(unittest.TestCase):
    def test_down_up_triggers_exactly_one_upstream_rejoin(self):
        with TemporaryDirectory() as root:
            ready, receipt = Path(root)/"ready", Path(root)/"receipt"
            with patch("scripts.mesh_peer_autorejoin.interface_is_up",
                       side_effect=[True, True, False, False, True]), \
                 patch("scripts.mesh_peer_autorejoin.group_rejoin",
                       return_value=True) as action, \
                 patch("scripts.mesh_peer_autorejoin.time.sleep"):
                code = supervise("cmesh-123-b", "meshB", root, 0,
                                 ready, receipt, 5, 0.05)
            self.assertEqual(code, 0)
            self.assertEqual(action.call_count, 1)
            self.assertEqual(receipt.read_text(), "SUPERVISOR_REJOIN=PASS\n")

    def test_no_link_down_cannot_fabricate_recovery(self):
        with TemporaryDirectory() as root:
            ready, receipt = Path(root)/"ready", Path(root)/"receipt"
            with patch("scripts.mesh_peer_autorejoin.interface_is_up",
                       return_value=True), \
                 patch("scripts.mesh_peer_autorejoin.time.monotonic",
                       side_effect=[0, 10]), \
                 patch("scripts.mesh_peer_autorejoin.group_rejoin") as action:
                code = supervise("cmesh-123-b", "meshB", root, 0,
                                 ready, receipt, 5, 0.05)
            self.assertEqual(code, 1)
            action.assert_not_called()
            self.assertFalse(receipt.exists())

    def test_refuses_real_device_namespace(self):
        with TemporaryDirectory() as root:
            with self.assertRaises(ValueError):
                supervise("default", "wlan0", root, 0,
                          Path(root)/"ready", Path(root)/"receipt", 5, 0.05)


if __name__ == "__main__":
    unittest.main()
