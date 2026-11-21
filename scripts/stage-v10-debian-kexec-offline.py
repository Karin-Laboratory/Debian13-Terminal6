#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Offline-only inspection and candidate staging for P25 loader -> Debian proto2.
Never contacts a device and never modifies its input artifacts.
"""
import argparse
import hashlib
import json
import re
import shutil
import struct
import zipfile
from pathlib import Path, PurePosixPath

KERNEL = "6.18.63-debian-t6-proto2"
OLD_P44_SHA = "9aded7613ffc262060501d633dd2d27600a544b5fd7d35a6bdbeb25ff9b28f09"
OLD_SIGNED_P25_SHA = "74c1c98b31cdba54f71d16f1983fbeff347bb334c5ae7d7f1353cd57f734936e"
P43_PREFIX = "terminal6/debian/"

def sha(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()

def validate_path(p):
    path = PurePosixPath(p)
    if not p or p.startswith("/") or "\\" in p or ".." in path.parts or str(path) != p:
        raise ValueError("unsafe archive path: " + p)

def verify_p44(path):
    if sha(path) != OLD_P44_SHA:
        raise ValueError("P44 archive differs from retained proto2 candidate")
    with zipfile.ZipFile(path) as z:
        names = z.namelist()
        if len(names) != len(set(names)):
            raise ValueError("duplicate ZIP entries")
        for name in names:
            validate_path(name.rstrip("/"))
        if z.testzip() is not None:
            raise ValueError("P44 ZIP CRC failed")
        for required in ("manifest.json", "SHA256SUMS", "rootfs.tar.gz", "modules.tar"):
            if required not in names:
                raise ValueError("P44 ZIP missing " + required)
        manifest = json.loads(z.read("manifest.json"))
        if manifest.get("kernel_release") != KERNEL:
            raise ValueError("P44 kernel ABI mismatch")
        pair = manifest.get("p25_signed_boot_tested", {})
        if pair.get("sha256") != OLD_SIGNED_P25_SHA:
            raise ValueError("P44 ZIP does not identify boot-proven proto2 P25")
        for name in ("rootfs.tar.gz", "modules.tar"):
            record = manifest["files"][name]
            h = hashlib.sha256()
            size = 0
            with z.open(name) as f:
                for chunk in iter(lambda: f.read(1024 * 1024), b""):
                    h.update(chunk); size += len(chunk)
            if h.hexdigest() != record["sha256"] or size != record["bytes"]:
                raise ValueError("P44 inner mismatch: " + name)
        return manifest

def verify_arm64_image(path):
    with path.open("rb") as f:
        header = f.read(64)
    if len(header) < 64 or header[56:60] != b"ARM\\x64":
        raise ValueError("not an ARM64 raw Linux Image (Image header magic)")
    return path.stat().st_size

def verify_dtb(path):
    with path.open("rb") as f:
        header = f.read(40)
    if len(header) != 40 or struct.unpack(">I", header[:4])[0] != 0xd00dfeed:
        raise ValueError("invalid FDT magic")
    declared = struct.unpack(">I", header[4:8])[0]
    if declared > path.stat().st_size or declared < 40:
        raise ValueError("invalid FDT totalsize")
    return declared

def stage(args):
    image, dtb, p44, out = map(Path, (args.image, args.dtb, args.p44_zip, args.output))
    if out.exists():
        raise ValueError("refuse overwrite destination: " + str(out))
    for file in (image, dtb, p44):
        if not file.is_file():
            raise ValueError("missing input: " + str(file))
    verify_arm64_image(image)
    verify_dtb(dtb)
    existing = verify_p44(p44)
    initrd = Path(args.initrd) if args.initrd else None
    if initrd and (not initrd.is_file() or initrd.stat().st_size == 0):
        raise ValueError("bad initrd")
    out.mkdir(parents=True)
    assets = {"Image": image, "board.dtb": dtb}
    if initrd:
        assets["initrd.img"] = initrd
    expected = {}
    try:
        osdir = out / P43_PREFIX
        osdir.mkdir(parents=True)
        for name, src in assets.items():
            dest = osdir / name
            shutil.copyfile(src, dest)
            expected[P43_PREFIX + name] = {"bytes": dest.stat().st_size, "sha256": sha(dest)}
            if sha(src) != sha(dest):
                raise ValueError("staged copy mismatch")
        metadata = {
            "schema": "terminal6-kexec-debian-preflight-v1",
            "status": "OFFLINE_STAGED_NOT_HARDWARE_TESTED",
            "kernel_release": KERNEL,
            "p43_assets": expected,
            "p44_existing_candidate": {"sha256": sha(p44), "bytes": p44.stat().st_size,
                "source_commit": existing.get("source_commit"),
                "warning": "proto2-specific rootfs; NOT proven with new kexec loader"},
            "p25_loader": "P25 remains unchanged; no P25 bytes in this package",
            "required_hardware_checks": ["P25 5-gate PASS", "P43 ext4 ro,noload",
                "actual root PARTNAME", "rootfs existing state and backup",
                "kexec_load", "kexec_execute", "Debian LAN and SSH"],
        }
        (out / "manifest.json").write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n")
        (out / "SHA256SUMS").write_text("".join(
            v["sha256"] + "  " + name + "\n" for name, v in sorted(expected.items())))
        example = [
            "# TEMPLATE ONLY. Must set root= and verify actual PARTNAME/rootfs location.",
            "# Do NOT copy to /config until verified by owner and loader gate PASS.",
            "kernel=terminal6/debian/Image", "dtb=terminal6/debian/board.dtb",
        ]
        if initrd:
            example.append("initrd=terminal6/debian/initrd.img")
        example.append("cmdline=REPLACE_WITH_VERIFIED_CONSOLE_AND_ROOT_CMDLINE")
        (out / "debian.conf.EXAMPLE").write_text("\n".join(example) + "\n")
        (out / "boot.conf.EXAMPLE").write_text(
            "# Hold autoboot until authorized kexec preflight\n"
            "default=debian\nnext=\nautoboot=0\ntimeout=15\n")
        print("OFFLINE_P43_CANDIDATE_STAGED_NOT_BOOT_TESTED", out)
        print("P44_EXISTING_CANDIDATE_VERIFIED", sha(p44))
    except BaseException:
        shutil.rmtree(out)
        raise

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--image", required=True)
    ap.add_argument("--dtb", required=True)
    ap.add_argument("--p44-zip", required=True)
    ap.add_argument("--output", required=True)
    ap.add_argument("--initrd")
    args = ap.parse_args()
    try:
        stage(args)
    except (ValueError, KeyError, OSError, zipfile.BadZipFile) as e:
        ap.exit(2, "OFFLINE_PREFLIGHT_BLOCKED: " + str(e) + "\n")

if __name__ == "__main__":
    main()
