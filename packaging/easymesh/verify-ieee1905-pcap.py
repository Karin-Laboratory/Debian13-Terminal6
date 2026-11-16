#!/usr/bin/env python3
"""Validate IEEE1905.1 topology exchange in captured Ethernet PCAP, without transmitting."""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import re
import struct
import sys

ETH_P_1905 = 0x893A
VLAN_TYPES = {0x8100, 0x88A8, 0x9100}
MAX_CAPTURE_SIZE = 16 * 1024 * 1024
MAC_RE = re.compile(r"^(?:[0-9a-fA-F]{2}:){5}[0-9a-fA-F]{2}$")


class CaptureError(ValueError):
    pass


def mac_bytes(text: str) -> bytes:
    if not MAC_RE.fullmatch(text):
        raise CaptureError("expected six-octet MAC address")
    return bytes.fromhex(text.replace(":", ""))


def packets(raw: bytes):
    if len(raw) < 24:
        raise CaptureError("truncated PCAP header")
    magic = bytes(raw[:4])
    endian = {b"\xd4\xc3\xb2\xa1": "<", b"\xa1\xb2\xc3\xd4": ">",
              b"\x4d\x3c\xb2\xa1": "<", b"\xa1\xb2\x3c\x4d": ">"}.get(magic)
    if endian is None:
        raise CaptureError("unsupported PCAP format (classic Ethernet PCAP required)")
    major, minor, _zone, _accuracy, snaplen, network = struct.unpack_from(endian + "HHiiII", raw, 4)
    if (major, minor) != (2, 4) or network != 1 or not (14 <= snaplen <= MAX_CAPTURE_SIZE):
        raise CaptureError("PCAP must contain Ethernet DLT=1 frames")
    position = 24
    while position < len(raw):
        if len(raw) - position < 16:
            raise CaptureError("truncated PCAP packet header")
        sec, usec, caplen, original = struct.unpack_from(endian + "IIII", raw, position)
        position += 16
        if caplen > snaplen or caplen > original or caplen > MAX_CAPTURE_SIZE or caplen > len(raw) - position:
            raise CaptureError("invalid or truncated PCAP frame")
        yield (sec, usec), raw[position:position + caplen]
        position += caplen


def parse_frame(frame: bytes):
    if len(frame) < 14:
        return None
    dst, src = frame[:6], frame[6:12]
    ethertype = int.from_bytes(frame[12:14], "big")
    offset = 14
    for _ in range(2):
        if ethertype not in VLAN_TYPES:
            break
        if len(frame) < offset + 4:
            raise CaptureError("truncated VLAN tag")
        ethertype = int.from_bytes(frame[offset + 2:offset + 4], "big")
        offset += 4
    if ethertype != ETH_P_1905:
        return None
    data = frame[offset:]
    if len(data) < 8:
        raise CaptureError("truncated IEEE 1905 CMDU")
    version, reserved, msg_type, mid, frag, flags = struct.unpack_from("!BBHHBB", data)
    if version != 0 or reserved != 0:
        raise CaptureError("unsupported IEEE 1905 CMDU version")
    if not (flags & 0x80) or frag != 0:
        return {"type": msg_type, "mid": mid, "src": src, "dst": dst,
                "complete": False, "tlvs": {}}
    tlvs: dict[int, list[bytes]] = {}
    pos = 8
    eof = False
    while pos + 3 <= len(data):
        t = data[pos]
        size = int.from_bytes(data[pos + 1:pos + 3], "big")
        pos += 3
        if pos + size > len(data):
            raise CaptureError("truncated IEEE 1905 TLV")
        value = data[pos:pos + size]
        pos += size
        if t == 0:
            if size != 0:
                raise CaptureError("malformed end-of-message TLV")
            eof = True
            break
        tlvs.setdefault(t, []).append(value)
    if not eof or any(data[pos:]):
        raise CaptureError("missing end-of-message TLV or non-zero padding")
    return {"type": msg_type, "mid": mid, "src": src, "dst": dst,
            "complete": True, "tlvs": tlvs}


def inspect_pcap(raw: bytes, controller_al: bytes, agent_al: bytes) -> dict:
    if controller_al == agent_al or controller_al[0] & 1 or agent_al[0] & 1:
        raise CaptureError("controller and agent must have distinct unicast AL MACs")
    discovered: set[bytes] = set()
    interface_to_al: dict[bytes, bytes] = {}
    queries: set[int] = set()
    responses: set[int] = set()
    types: Counter[int] = Counter()
    total = accepted = 0
    for _, ethernet in packets(raw):
        total += 1
        frame = parse_frame(ethernet)
        if frame is None:
            continue
        accepted += 1
        types[frame["type"]] += 1
        if not frame["complete"]:
            continue
        tlvs = frame["tlvs"]
        if frame["type"] == 0:
            for value in tlvs.get(1, []):
                if len(value) == 6 and value in {controller_al, agent_al}:
                    discovered.add(value)
                    interface_to_al[frame["src"]] = value
        elif frame["type"] == 2:
            if (frame["dst"] in (agent_al, *[k for k, v in interface_to_al.items() if v == agent_al])
                    and interface_to_al.get(frame["src"], frame["src"]) == controller_al):
                queries.add(frame["mid"])
        elif frame["type"] == 3:
            agent_reply = (interface_to_al.get(frame["src"], frame["src"]) == agent_al and
                           frame["dst"] in (controller_al, *[k for k, v in interface_to_al.items() if v == controller_al]) and
                           any(len(v) >= 6 and v[:6] == agent_al for v in tlvs.get(3, [])))
            if agent_reply:
                responses.add(frame["mid"])
    verdict = {
        "capture_kind": "pcap-real-or-synthetic-not-attested",
        "frames_observed": total,
        "ieee1905_cmdus_observed": accepted,
        "message_type_counts": {str(k): types[k] for k in sorted(types)},
        "controller_discovery": controller_al in discovered,
        "agent_discovery": agent_al in discovered,
        "controller_query_agent": bool(queries),
        "agent_topology_response": bool(responses),
        "correlated_query_response": bool(queries & responses),
        "topology_database_verified": False,
        "agent_loss_detection_verified": False,
    }
    verdict["wire_topology_exchange"] = all(verdict[k] for k in (
        "controller_discovery", "agent_discovery", "controller_query_agent",
        "agent_topology_response", "correlated_query_response"))
    return verdict


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--pcap", type=Path, required=True, help="classic Ethernet PCAP, not pcapng")
    ap.add_argument("--controller-al", type=mac_bytes, required=True)
    ap.add_argument("--agent-al", type=mac_bytes, required=True)
    args = ap.parse_args()
    try:
        if args.pcap.stat().st_size > MAX_CAPTURE_SIZE:
            raise CaptureError("capture exceeds configured maximum size")
        result = inspect_pcap(args.pcap.read_bytes(), args.controller_al, args.agent_al)
    except (OSError, CaptureError) as exc:
        print(json.dumps({"verdict": "INVALID", "reason": str(exc)}, sort_keys=True), file=sys.stderr)
        return 2
    result["verdict"] = "WIRE_TOPOLOGY_PASS" if result["wire_topology_exchange"] else "WIRE_TOPOLOGY_NOT_PROVEN"
    print(json.dumps(result, sort_keys=True))
    return 0 if result["wire_topology_exchange"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
