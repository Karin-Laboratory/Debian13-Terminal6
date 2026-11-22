"""Synthetic PCAP fixtures, never evidence of live IEEE1905 device communication."""
import importlib.util
from pathlib import Path
import struct
import unittest

SCRIPT = Path(__file__).parents[1] / "packaging/easymesh/verify-ieee1905-pcap.py"
spec = importlib.util.spec_from_file_location("verify_ieee1905_pcap", SCRIPT)
module = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(module)

A = bytes.fromhex("02000000000a")
B = bytes.fromhex("02000000000b")
MULTICAST = bytes.fromhex("0180c2000013")


def tlv(t, b):
    return bytes([t]) + struct.pack("!H", len(b)) + b


def frame(dst, src, msg, mid=1, payload=b"", *, vlan=False):
    e = dst + src
    e += (b"\x81\x00\x00\x01" if vlan else b"") + b"\x89\x3a"
    e += struct.pack("!BBHHBB", 0, 0, msg, mid, 0, 0x80)
    return e + payload + b"\x00\x00\x00"


def pcap(frames):
    header = b"\xd4\xc3\xb2\xa1" + struct.pack("<HHiiII", 2, 4, 0, 0, 65535, 1)
    return header + b"".join(struct.pack("<IIII", 100 + i, 0, len(f), len(f)) + f
                             for i, f in enumerate(frames))


def scenario():
    return [frame(MULTICAST, A, 0, payload=tlv(1, A)),
            frame(MULTICAST, B, 0, payload=tlv(1, B), vlan=True),
            frame(B, A, 2, mid=31),
            frame(A, B, 3, mid=31, payload=tlv(3, B + b"\x01\x00"))]


class CaptureTests(unittest.TestCase):
    def test_synthetic_topology_sequence_passes_parser_only(self):
        verdict = module.inspect_pcap(pcap(scenario()), A, B)
        self.assertTrue(verdict["wire_topology_exchange"])
        self.assertEqual(verdict["ieee1905_cmdus_observed"], 4)
        self.assertFalse(verdict["topology_database_verified"])

    def test_agent_discovery_missing_is_not_proof(self):
        frames = scenario()
        self.assertFalse(module.inspect_pcap(pcap([frames[0], frames[2], frames[3]]), A, B)
                         ["wire_topology_exchange"])

    def test_unmatched_mid_is_not_proof(self):
        frames = scenario()
        frames[-1] = frame(A, B, 3, mid=32, payload=tlv(3, B + b"\x01\x00"))
        self.assertFalse(module.inspect_pcap(pcap(frames), A, B)["correlated_query_response"])

    def test_response_requires_correct_agent_device_info(self):
        frames = scenario()
        frames[-1] = frame(A, B, 3, mid=31, payload=tlv(3, A + b"\x01\x00"))
        self.assertFalse(module.inspect_pcap(pcap(frames), A, B)["agent_topology_response"])

    def test_non_ethernet_linktype_rejected(self):
        raw = bytearray(pcap(scenario()))
        raw[20:24] = struct.pack("<I", 113)
        with self.assertRaisesRegex(module.CaptureError, "Ethernet"):
            module.inspect_pcap(raw, A, B)

    def test_truncated_capture_rejected(self):
        with self.assertRaisesRegex(module.CaptureError, "invalid or truncated"):
            module.inspect_pcap(pcap(scenario())[:-1], A, B)

    def test_truncated_tlv_rejected(self):
        malformed = frame(MULTICAST, A, 0, payload=b"\x01\xff\xff")
        with self.assertRaisesRegex(module.CaptureError, "truncated IEEE 1905 TLV"):
            module.inspect_pcap(pcap([malformed]), A, B)

    def test_non_1905_ethertype_not_counted(self):
        raw = bytearray(scenario()[0])
        raw[12:14] = b"\x08\x00"
        self.assertEqual(module.inspect_pcap(pcap([raw]), A, B)["ieee1905_cmdus_observed"], 0)

    def test_nonzero_padding_rejected(self):
        with self.assertRaisesRegex(module.CaptureError, "non-zero padding"):
            module.inspect_pcap(pcap([scenario()[0] + b"\x01"]), A, B)

    def test_identical_al_mac_rejected(self):
        with self.assertRaisesRegex(module.CaptureError, "distinct"):
            module.inspect_pcap(pcap(scenario()), A, A)

    def test_invalid_al_mac_rejected(self):
        with self.assertRaisesRegex(module.CaptureError, "six-octet"):
            module.mac_bytes("nonsense")

    def test_nonfinal_fragment_not_counted_as_response(self):
        frames = scenario()
        raw = bytearray(frames[-1])
        raw[21] = 0
        frames[-1] = raw
        self.assertFalse(module.inspect_pcap(pcap(frames), A, B)["agent_topology_response"])

    def test_interface_mac_may_differ_from_al_mac(self):
        iface_a, iface_b = bytes.fromhex("021000000001"), bytes.fromhex("021000000002")
        frames = [frame(MULTICAST, iface_a, 0, payload=tlv(1, A)),
                  frame(MULTICAST, iface_b, 0, payload=tlv(1, B)),
                  frame(iface_b, iface_a, 2, mid=42),
                  frame(iface_a, iface_b, 3, mid=42, payload=tlv(3, B + b"\x00"))]
        self.assertTrue(module.inspect_pcap(pcap(frames), A, B)["wire_topology_exchange"])


if __name__ == "__main__":
    unittest.main()
