#!/usr/bin/env python3
"""Fail-closed 802.11s host PCAP summary. No packet bytes or secrets are printed.

Recognizes classic libpcap with Radiotap (DLT 127) or IEEE 802.11 (DLT 105).
AMPE uses a 16-byte MIC IE (EID 76) followed by AES-SIV ciphertext within
mesh peering management action frames. Seeing a MIC does *not* independently
validate its cryptographic authenticity. SAE auth and protected data are
separate mandatory observations. This is a safe PCAP summary, not decryption.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
import struct
import sys


PCAP_MAGIC = {
    b"\xd4\xc3\xb2\xa1": "<",
    b"\xa1\xb2\xc3\xd4": ">",
    b"\x4d\x3c\xb2\xa1": "<",
    b"\xa1\xb2\x3c\x4d": ">",
}


def frames_from_pcap(data: bytes):
    if len(data) < 24 or data[:4] not in PCAP_MAGIC:
        raise ValueError("input is not a classic libpcap capture")
    endian = PCAP_MAGIC[data[:4]]
    linktype = struct.unpack_from(endian + "I", data, 20)[0] & 0xFFFF
    if linktype not in (105, 127):
        raise ValueError("unsupported capture link type")
    offset = 24
    frame_count = 0
    while offset < len(data):
        if offset + 16 > len(data):
            raise ValueError("truncated pcap record")
        _, _, incl, original = struct.unpack_from(endian + "IIII", data, offset)
        offset += 16
        if incl == 0 or incl > 4 * 1024 * 1024 or incl > original:
            raise ValueError("invalid pcap capture length")
        if offset + incl > len(data):
            raise ValueError("truncated packet")
        record = data[offset:offset + incl]
        offset += incl
        if linktype == 127:
            if len(record) < 8:
                raise ValueError("truncated radiotap header")
            rt_len = int.from_bytes(record[2:4], "little")
            if rt_len < 8 or rt_len > len(record):
                raise ValueError("invalid radiotap header")
            record = record[rt_len:]
        frame_count += 1
        yield record
    if frame_count == 0:
        raise ValueError("empty packet capture")


def audit(data: bytes) -> dict:
    evidence = defaultdict(set)
    totals = Counter()
    for payload in frames_from_pcap(data):
        if len(payload) < 26:
            continue
        fc = int.from_bytes(payload[:2], "little")
        kind, subtype = (fc >> 2) & 3, (fc >> 4) & 15
        source = ":".join(f"{x:02x}" for x in payload[10:16])
        if kind == 0 and subtype == 11:
            # Open System auth=0; SAE auth algorithm=3.
            if int.from_bytes(payload[24:26], "little") == 3:
                totals["sae_auth"] += 1
                evidence["sae_auth"].add(source)
        if kind == 0 and subtype == 13 and len(payload) >= 48:
            # IEEE 802.11 Self-protected category=15, Mesh Peer Open/Confirm.
            if payload[24] == 15 and payload[25] in (1, 2):
                # EID_MIC=76, len=16; following body is AES-SIV ciphertext.
                # A MIC marker in a random byte string is not a valid proof
                # of authenticity: the protected-data and peer/IP gates are
                # separately required by the enclosing runtime test.
                mic = payload.find(b"\x4c\x10", 26)
                if mic != -1 and len(payload) - (mic + 18) >= 20:
                    category = ("ampe_open" if payload[25] == 1
                                else "ampe_confirm")
                    totals[category] += 1
                    evidence[category].add(source)
        if kind == 2 and (fc & 0x4000):
            totals["protected_data"] += 1
            evidence["protected_data"].add(source)
    # Require two distinct independently observed transmitters. Do not
    # merely trust a 'key_mgmt=SAE' config string or supplicant startup.
    checks = {
        "SAE_AUTH_FRAMES": len(evidence["sae_auth"]) >= 2,
        "AMPE_MIC_OPEN": len(evidence["ampe_open"]) >= 2,
        "AMPE_MIC_CONFIRM": len(evidence["ampe_confirm"]) >= 2,
        "PROTECTED_DATA_FRAMES": len(evidence["protected_data"]) >= 2,
    }
    # Do not include actual MACs/handshake frames in public output.
    return {"pass": all(checks.values()), "checks": checks,
            "frame_counts": dict(totals),
            "distinct_transmitters": {key: len(value) for key, value
                                       in evidence.items()},
            "scope": "hwsim on-wire formats; no MIC decryption/validation"}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pcap", type=Path, required=True)
    parser.add_argument("--output", type=Path,
                        help="sanitized JSON summary only; never upload pcap")
    args = parser.parse_args()
    try:
        report = audit(args.pcap.read_bytes())
    except (OSError, ValueError, struct.error) as exc:
        print("HWSIM_PCAP_AUDIT=FAIL:" + type(exc).__name__, file=sys.stderr)
        return 1
    for key, passed in report["checks"].items():
        print(f"HWSIM_{key}={'PASS' if passed else 'FAIL'}")
    print("HWSIM_AMPE_CRYPTOGRAPHIC_MIC_VALIDATION=NOT_INDEPENDENTLY_PERFORMED")
    print("HWSIM_PCAP_AUDIT=" + ("PASS" if report["pass"] else "FAIL"))
    if args.output:
        args.output.write_text(json.dumps(report, sort_keys=True, indent=2) + "\n",
                               encoding="utf-8")
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
