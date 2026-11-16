#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Assemble a template-free, unsigned Android boot-v2 ENGINEERING CANDIDATE.

Uses the SHA-pinned upstream MT6990 boot-v2 packer. This removes the private
unsigned-P25 *template* as a manufacturing input, but does NOT establish that
the public board DTS, boot addresses or raw-DTB layout satisfy SBA6D LK.
Never signs, flashes, or marks a candidate safe to boot.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile

SIZE = 33554432
PAGE = 2048
HEADROOM = 8192 + 262144
PACKER_BLOB = "00e2abd7f1aa427145ab547587702f349ecc789c"
REQUIRED = {"cmdline", "dtb_addr", "header_size", "header_version",
            "kernel_addr", "name", "os_version", "page_size", "ramdisk_addr",
            "second_addr", "tags_addr"}


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def git_blob_sha(data: bytes) -> str:
    return hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()


def check_meta(doc: object) -> None:
    if not isinstance(doc, dict) or set(doc) != REQUIRED:
        raise ValueError("profile must contain exact boot-v2 metadata fields")
    if doc["header_version"] != 2 or doc["header_size"] != 1660 or doc["page_size"] != PAGE:
        raise ValueError("expected Android boot header v2 / 2048-byte page")
    for k in ("kernel_addr", "ramdisk_addr", "second_addr", "tags_addr", "os_version"):
        if type(doc[k]) is not int or not 0 <= doc[k] <= 0xFFFFFFFF:
            raise ValueError("invalid 32-bit metadata: " + k)
    if type(doc["dtb_addr"]) is not int or not 0 <= doc["dtb_addr"] < (1 << 64):
        raise ValueError("invalid DTB address")
    if not isinstance(doc["name"], str) or len(doc["name"].encode("ascii")) > 15:
        raise ValueError("invalid board name")
    if not isinstance(doc["cmdline"], str) or len(doc["cmdline"].encode("ascii")) > 1534:
        raise ValueError("invalid cmdline")


def require_file(path: Path, size_limit: int) -> bytes:
    if not path.is_absolute() or not path.is_file() or path.is_symlink():
        raise ValueError("input must be an absolute regular file")
    if path.stat().st_size > size_limit:
        raise ValueError("oversized input")
    return path.read_bytes()


def verify_image(raw: bytes, kernel: bytes, dtb: bytes, profile: dict) -> None:
    if len(raw) >= SIZE - HEADROOM or raw[:8] != b"ANDROID!":
        raise ValueError("boot image layout/header/headroom invalid")
    header = struct.unpack_from("<10I", raw, 8)
    # kernel-size, kernel-address, ramdisk-size/address, second-size/address,
    # tags-address, page-size, header-version, os-version
    if (header[0] == 0 or header[2] != 0 or header[4] != 0 or
            header[7] != PAGE or header[8] != 2 or
            header[0] != len(gzip.compress(kernel, compresslevel=9, mtime=0))):
        raise ValueError("unexpected kernel/section sizes")
    if struct.unpack_from("<I", raw, 1644)[0] != 1660:
        raise ValueError("invalid header size")
    if struct.unpack_from("<I", raw, 1648)[0] != len(dtb):
        raise ValueError("incorrect raw DTB section size")
    if struct.unpack_from("<Q", raw, 1652)[0] != profile["dtb_addr"]:
        raise ValueError("incorrect DTB load address")
    dtboff = PAGE + ((header[0] + PAGE - 1) // PAGE) * PAGE
    if raw[dtboff:dtboff + len(dtb)] != dtb:
        raise ValueError("DTB payload mismatch")
    if raw[1660:PAGE].strip(b"\0") or raw[dtboff + len(dtb):].strip(b"\0"):
        raise ValueError("nonzero padding")


def build(stage: Path, profile_path: Path, image_path: Path, initramfs_path: Path,
          dtb_path: Path, output: Path) -> dict:
    if not output.is_absolute() or output == Path("/") or output.exists() or output.is_symlink():
        raise ValueError("output must be a new absolute directory")
    if not output.parent.is_dir() or any(p.is_symlink() for p in output.parents):
        raise ValueError("output parent must not be symlinked")
    packer = stage / "tools/public-donor/lg6851f_mkbootimg_v2.py"
    packer_data = require_file(packer, 100000)
    if git_blob_sha(packer_data) != PACKER_BLOB:
        raise ValueError("upstream packer identity mismatch")
    receipt = json.loads(require_file(stage / "source-receipt.json", 100000).decode("utf-8"))
    if receipt.get("status") != "PUBLIC_TEXT_STAGED_NOT_BOOT_VALIDATED" or not any(
        x.get("git_blob_sha1") == PACKER_BLOB for x in receipt.get("files", [])
    ):
        raise ValueError("unverified staged source provenance")
    profile_bytes = require_file(profile_path, 16384)
    profile = json.loads(profile_bytes)
    check_meta(profile)
    kernel = require_file(image_path, 35000000)
    cpio = require_file(initramfs_path, 12000000)
    dtb = require_file(dtb_path, 3000000)
    if len(kernel) < 64 or kernel[56:60] != b"ARM\x64":
        raise ValueError("kernel is not an ARM64 Image")
    if kernel.count(cpio) != 1 or b"rootfs_data" not in gzip.decompress(cpio):
        raise ValueError("Debian P44 initramfs is not embedded exactly once")
    if len(dtb) < 40 or dtb[:4] != b"\xd0\x0d\xfe\xed":
        raise ValueError("raw DTB FDT magic missing")
    if struct.unpack_from(">I", dtb, 4)[0] not in range(40, len(dtb) + 1):
        raise ValueError("DTB total size invalid")
    temp = Path(tempfile.mkdtemp(prefix=".p25-public-candidate-", dir=output.parent))
    try:
        temp_profile = temp / "profile.json"
        temp_profile.write_bytes(profile_bytes)
        rawpath = temp / "unpacked.img"
        subprocess.run([sys.executable, str(packer), "--meta", str(temp_profile),
                        "--kernel", str(image_path), "--dtb", str(dtb_path),
                        "--out", str(rawpath)], check=True, stdout=subprocess.PIPE,
                       stderr=subprocess.PIPE, timeout=120)
        raw = require_file(rawpath, SIZE)
        verify_image(raw, kernel, dtb, profile)
        p25 = raw + bytes(SIZE - len(raw))
        (temp / "p25-unsigned.img").write_bytes(p25)
        rawpath.unlink()
        rec = {"schema": 1, "status": "UNSIGNED_TEMPLATE_FREE_NOT_LK_VALIDATED",
               "unsigned_p25_bytes": SIZE, "unsigned_p25_sha256": sha(p25),
               "kernel_image_sha256": sha(kernel),
               "initramfs_sha256": sha(cpio), "dtb_sha256": sha(dtb),
               "profile_sha256": sha(profile_bytes), "upstream_packer_blob": PACKER_BLOB,
               "note": "Raw DTB, no private template/vendor64, no boot/compatibility proof"}
        (temp / "p25-receipt.json").write_text(json.dumps(rec, indent=2) + "\n")
        os.replace(temp, output)
        return rec
    finally:
        if temp.exists():
            shutil.rmtree(temp)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source-stage", required=True, type=Path)
    p.add_argument("--profile", required=True, type=Path)
    p.add_argument("--kernel-image", required=True, type=Path)
    p.add_argument("--initramfs-cpio-gz", required=True, type=Path)
    p.add_argument("--dtb", required=True, type=Path)
    p.add_argument("--output", required=True, type=Path)
    a = p.parse_args()
    rec = build(a.source_stage, a.profile, a.kernel_image,
                a.initramfs_cpio_gz, a.dtb, a.output)
    print(rec["status"], rec["unsigned_p25_sha256"])


if __name__ == "__main__":
    main()
