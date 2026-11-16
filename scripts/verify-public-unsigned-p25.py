#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Independent full unsigned P25 readback, without using the image producer.

Checks outer Android boot-v2, standard AOSP single-entry DT table, exact
kernel/DTB/P44 initramfs inputs, zero padding, boot id and SHA receipt.
A structural PASS is NOT an LK boot/signature/device functional PASS.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from pathlib import Path
import struct

PARTITION_SIZE = 33554432
PAGE = 2048
MAGIC = b"ANDROID!"
FDT = bytes.fromhex("d00dfeed")


def check(p25: bytes, image: bytes, bare_dtb: bytes, cpio: bytes,
          profile: dict, receipt: dict) -> dict:
    def fail(message):
        raise ValueError(message)

    if len(p25) != PARTITION_SIZE or p25[:8] != MAGIC:
        fail("P25 size/magic mismatch")
    fields = struct.unpack_from("<10I", p25, 8)
    kernel_size, kaddr, rsize, raddr, ssize, saddr, tags, pages, version, osver = fields
    if any((rsize, ssize, struct.unpack_from("<I", p25, 1632)[0])):
        fail("unexpected nonempty boot-v2 sections")
    if pages != PAGE or version != 2 or struct.unpack_from("<I", p25, 1644)[0] != 1660:
        fail("boot v2 page/version/header mismatch")
    if (kaddr, raddr, saddr, tags, osver) != tuple(profile[k] for k in
        ("kernel_addr", "ramdisk_addr", "second_addr", "tags_addr", "os_version")):
        fail("boot address metadata differs from public profile")
    if struct.unpack_from("<Q", p25, 1652)[0] != profile["dtb_addr"]:
        fail("DTB load address mismatch")
    command = (p25[64:576]+p25[608:1632]).split(bytes([0]), 1)[0].decode("ascii")
    if command != profile["cmdline"]:
        fail("Debian command line mismatch")
    if p25[48:64].split(bytes([0]), 1)[0].decode("ascii") != profile["name"]:
        fail("board name mismatch")
    if p25[1660:PAGE] != bytes(PAGE-1660):
        fail("nonzero boot header padding")
    if image[56:60] != b"ARM\x64" or image.count(cpio) != 1:
        fail("source Image or P44 initramfs identity mismatch")
    if not bare_dtb.startswith(FDT) or struct.unpack_from(">I", bare_dtb, 4)[0] != len(bare_dtb):
        fail("source FDT invalid")
    kstart = PAGE
    kend = kstart + kernel_size
    if not 0 < kernel_size < PARTITION_SIZE // 2:
        fail("kernel compressed size bound")
    if gzip.decompress(p25[kstart:kend]) != image:
        fail("kernel decompression/readback mismatch")
    dtoff = PAGE + ((kernel_size + PAGE - 1) // PAGE) * PAGE
    dtlen = struct.unpack_from("<I", p25, 1648)[0]
    if dtlen != len(bare_dtb)+64 or dtoff + dtlen > PARTITION_SIZE:
        fail("DTB section bounds")
    table = p25[dtoff:dtoff+dtlen]
    head = struct.unpack_from(">8I", table)
    entry = struct.unpack_from(">8I", table, 32)
    if head != (0xd7b7ab1e, dtlen, 32, 32, 1, 32, PAGE, 0):
        fail("AOSP dt_table_header not valid")
    if entry != (len(bare_dtb), 64, 0, 0, 0, 0, 0, 0):
        fail("AOSP dt_table_entry mismatch")
    if table[64:] != bare_dtb:
        fail("DTB payload independently differs")
    if p25[kend:dtoff] != bytes(dtoff-kend):
        fail("nonzero kernel alignment padding")
    if p25[dtoff+dtlen:] != bytes(PARTITION_SIZE-dtoff-dtlen):
        fail("nonzero unsigned partition tail")
    h=hashlib.sha1()
    for part in (p25[kstart:kend], b"", b"", b"", table):
        h.update(part)
        h.update(struct.pack("<I", len(part)))
    if p25[576:608] != h.digest().ljust(32, bytes([0])):
        fail("Android boot ID mismatch")
    actual=hashlib.sha256(p25).hexdigest()
    if receipt.get("unsigned_p25_sha256") != actual:
        fail("manufacturing receipt SHA mismatch")
    return {"result": "PUBLIC_UNSIGNED_P25_INDEPENDENT_READBACK_PASS",
            "p25_bytes": len(p25), "p25_sha256": actual,
            "aosp_dtb_section_bytes": dtlen,
            "aosp_dtb_prefix_sha256": hashlib.sha256(table[:64]).hexdigest(),
            "device_lk_boot_tested": False, "signed": False}


def read(path: Path, maximum: int) -> bytes:
    if not path.is_absolute() or not path.is_file() or path.is_symlink():
        raise ValueError("input must be absolute non-symlink file")
    if path.stat().st_size > maximum:
        raise ValueError("oversized input")
    return path.read_bytes()


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    for p in ("p25","kernel-image","dtb","initramfs-cpio-gz","profile","receipt"):
        ap.add_argument("--"+p, required=True, type=Path)
    a=ap.parse_args()
    out=check(read(a.p25,PARTITION_SIZE),read(a.kernel_image,35000000),
              read(a.dtb,3000000),read(a.initramfs_cpio_gz,12000000),
              json.loads(read(a.profile,16384)),
              json.loads(read(a.receipt,16384)))
    print(json.dumps(out,sort_keys=True))


if __name__=="__main__":
    main()
