#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Derive public, non-secret Android boot-v2 header fields from a pinned release.

The published RC16 signed P25 is an observational REFERENCE only, not a
manufacturing template. No payload, signature, DTB or OEM bytes are reused.
The caller supplies a new Debian cmdline; never export the stock cmdline.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import struct

RC16_SHA256 = "4ee38fb3f85c7980889c5fe08f78a111069b485c9f7b8a13f09913430fa89787"
SIZE = 33554432
DEBIAN_CMDLINE = (
    "console=ttyS0,115200n8 earlycon keep_bootcon ignore_loglevel loglevel=8 "
    "root=PARTLABEL=rootfs_data rootfstype=ext4 rootwait rw"
)


def public_profile(raw: bytes, expected_sha: str = RC16_SHA256) -> dict:
    if len(raw) != SIZE or hashlib.sha256(raw).hexdigest() != expected_sha:
        raise ValueError("reference P25 length or release SHA mismatch")
    if raw[:8] != b"ANDROID!":
        raise ValueError("Android boot magic mismatch")
    vals = struct.unpack_from("<10I", raw, 8)
    kernel_size, kernel_addr, ramdisk_size, ramdisk_addr, second_size, second_addr, tags_addr, page_size, version, os_version = vals
    if page_size != 2048 or version != 2 or struct.unpack_from("<I", raw, 1644)[0] != 1660:
        raise ValueError("not the expected Android boot-v2 format")
    if any((ramdisk_size, second_size, struct.unpack_from("<I", raw, 1632)[0])):
        raise ValueError("unexpected nonempty section in reference")
    dtbsize = struct.unpack_from("<I", raw, 1648)[0]
    dtbaddr = struct.unpack_from("<Q", raw, 1652)[0]
    at = page_size + ((kernel_size + page_size - 1) // page_size) * page_size
    if at + dtbsize > SIZE or dtbsize < 104:
        raise ValueError("reference DTB bounds invalid")
    table = raw[at:at + dtbsize]
    head = struct.unpack_from(">8I", table)
    entry = struct.unpack_from(">8I", table, 32)
    if head != (0xd7b7ab1e, dtbsize, 32, 32, 1, 32, page_size, 0):
        raise ValueError("reference AOSP DT-table header mismatch")
    if entry != (dtbsize - 64, 64, 0, 0, 0, 0, 0, 0):
        raise ValueError("reference AOSP DT-table entry mismatch")
    if table[64:68] != b"\\xd0\\x0d\\xfe\\xed":
        raise ValueError("reference FDT magic mismatch")
    if struct.unpack_from(">I", table, 68)[0] != dtbsize - 64:
        raise ValueError("reference FDT total size mismatch")
    name = raw[48:64].split(b"\\0", 1)[0].decode("ascii")
    # The reference header is only used to extract public numeric addresses.
    # The Debian command line is independently authored and no OEM bytes are
    # embedded in output.
    return {"cmdline": DEBIAN_CMDLINE, "dtb_addr": dtbaddr,
            "header_size": 1660, "header_version": 2,
            "kernel_addr": kernel_addr, "name": name or "mt6990",
            "os_version": os_version, "page_size": page_size,
            "ramdisk_addr": ramdisk_addr, "second_addr": second_addr,
            "tags_addr": tags_addr}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--public-reference", required=True, type=Path)
    ap.add_argument("--output", required=True, type=Path)
    a = ap.parse_args()
    if not a.public_reference.is_absolute() or a.public_reference.is_symlink():
        ap.error("reference must be absolute non-symlink path")
    if not a.output.is_absolute() or a.output.exists():
        ap.error("output must be new absolute path")
    profile = public_profile(a.public_reference.read_bytes())
    a.output.write_text(json.dumps(profile, sort_keys=True, indent=2) + "\n")
    print("PUBLIC_RC16_BOOT_V2_PROFILE_OBSERVED_ONLY")
    print("NEW_DEBIAN_CMDLINE; NO_PRIVATE_TEMPLATE_OR_SIGNER")


if __name__ == "__main__":
    main()
