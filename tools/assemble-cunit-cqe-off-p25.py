#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Repack a pinned unsigned C-unit P25 with the CQE-off DTB; no signing/flash."""
from __future__ import annotations

import argparse
import gzip
import hashlib
from pathlib import Path
import struct

OLD_SHA = "9b7ed2a338b198813c75d299bd44645493da6dc052f177feaae974b83430a897"
OLD_DTB_SHA = "f9f24ba152d6714626b6c79c205cf190b3875629ef60d73357c769d2d2ea10e3"
NEW_DTB_SHA = "fb20c141ef71833cac20cd1deb13161c338ceac41843ad94fb5c81f4e1f0f6e9"
SIZE = 33_554_432


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def repack(old: bytes, dtb: bytes) -> bytes:
    if len(old) != SIZE or sha(old) != OLD_SHA or old[:8] != b"ANDROID!":
        raise ValueError("pinned unsigned P25 mismatch")
    if sha(dtb) not in (OLD_DTB_SHA, NEW_DTB_SHA):
        raise ValueError("DTB SHA mismatch")
    page = struct.unpack_from("<I", old, 36)[0]
    ksize = struct.unpack_from("<I", old, 8)[0]
    ssize = struct.unpack_from("<I", old, 1648)[0]
    if page != 2048 or struct.unpack_from("<I", old, 40)[0] != 2:
        raise ValueError("unexpected boot format")
    align = lambda n: (n + page - 1) // page * page
    kernel = old[page : page + ksize]
    if len(kernel) != ksize or gzip.decompress(kernel)[56:60] != b"ARM\x64":
        raise ValueError("kernel invalid")
    start = page + align(ksize)
    old_section = old[start : start + ssize]
    if len(old_section) != 64 + 148765 or sha(old_section[64:]) != OLD_DTB_SHA:
        raise ValueError("original DTB mismatch")
    section = old_section[:64] + dtb
    header = bytearray(old[:page])
    struct.pack_into("<I", header, 1648, len(section))
    boot_id = hashlib.sha1()
    for part in (kernel, b"", b"", b"", section):
        boot_id.update(part)
        boot_id.update(struct.pack("<I", len(part)))
    header[576:608] = boot_id.digest().ljust(32, b"\0")
    body = bytes(header) + kernel + bytes(align(ksize) - ksize)
    body += section + bytes(align(len(section)) - len(section))
    if len(body) > SIZE:
        raise ValueError("P25 overflow")
    return body + bytes(SIZE - len(body))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--old-unsigned", type=Path, required=True)
    parser.add_argument("--dtb", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists() or args.output.is_symlink():
        parser.error("output exists")
    old = args.old_unsigned.read_bytes()
    page = struct.unpack_from("<I", old, 36)[0]
    ksize = struct.unpack_from("<I", old, 8)[0]
    start = page + ((ksize + page - 1) // page) * page
    ssize = struct.unpack_from("<I", old, 1648)[0]
    original_dtb = old[start + 64 : start + ssize]
    if repack(old, original_dtb) != old:
        raise ValueError("original image cannot be rebuilt exactly")
    result = repack(old, args.dtb.read_bytes())
    with args.output.open("xb") as stream:
        stream.write(result)
    args.output.chmod(0o600)
    print(f"UNSIGNED_P25_BYTES={len(result)} SHA256={sha(result)}")


if __name__ == "__main__":
    main()
