#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""C-unit G1 self-kexec investigation: stage proven P25's ARM64 Image in RAM.

No boot-partition writes, no reboot, and deliberately NO 'kexec -e' action.
Requires an exact, operator-approved full 32MiB signed-P25 SHA-256.
A successful kexec -l is NOT evidence that the second Linux can boot.
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

SIGNED_P25_BYTES = 32 * 1024 * 1024
KNOWN_PROVEN_P25_SHA256 = "74c1c98b31cdba54f71d16f1983fbeff347bb334c5ae7d7f1353cd57f734936e"
EXPECTED_KERNEL_RELEASE = "6.18.63-debian-t6-proto2"
MAX_IMAGE_BYTES = 128 * 1024 * 1024


class GateError(Exception):
    pass


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read_fdt(path: Path) -> bytes:
    raw = path.read_bytes()
    if len(raw) < 40 or raw[:4] != b"\xd0\x0d\xfe\xed":
        raise GateError("FDT magic not present")
    total = struct.unpack_from(">I", raw, 4)[0]
    if total != len(raw):
        raise GateError(f"FDT totalsize mismatch: {total} != {len(raw)}")
    return raw


def extract_boot_v2(blob: bytes) -> bytes:
    """Extract an ARM64 Image from a known Android boot v2 P25, no writes."""
    if len(blob) != SIGNED_P25_BYTES:
        raise GateError(f"boot_a is not 32MiB ({len(blob)})")
    if blob[:8] != b"ANDROID!":
        raise GateError("not an Android boot image at partition offset zero")
    kernel_size, kernel_addr, ramdisk_size, ramdisk_addr, second_size, second_addr, tags_addr, page_size, version, os_version = struct.unpack_from("<10I", blob, 8)
    del kernel_addr, ramdisk_addr, second_addr, tags_addr, os_version
    if version != 2 or page_size != 2048 or not 0 < kernel_size < SIGNED_P25_BYTES - page_size:
        raise GateError("unsupported Android boot-v2 header layout")
    if ramdisk_size != 0 or second_size != 0:
        raise GateError("P25 has separate ramdisk/second stage; builtin initramfs cannot be assumed")
    compressed = blob[page_size:page_size + kernel_size]
    if not compressed.startswith(b"\x1f\x8b"):
        raise GateError("kernel payload is not gzip")
    try:
        image = gzip.decompress(compressed)
    except (OSError, EOFError) as ex:
        raise GateError(f"gzip decompression failed: {ex}") from ex
    if len(image) < 64 or len(image) > MAX_IMAGE_BYTES or image[56:60] != b"ARM\x64":
        raise GateError("decompressed kernel is not a valid-size ARM64 Image")
    return image


def read_and_check_p25(path: Path, expected_sha256: str) -> tuple[bytes, str]:
    if len(expected_sha256) != 64 or any(c not in "0123456789abcdef" for c in expected_sha256):
        raise GateError("expected P25 SHA-256 must be 64 lower-case hex characters")
    # No direct device writes. Avoid reading an unbounded block device.
    with path.open("rb", buffering=0) as handle:
        blob = handle.read(SIGNED_P25_BYTES + 1)
    if len(blob) != SIGNED_P25_BYTES:
        raise GateError("P25 partition is not exactly 32MiB")
    actual = digest(blob)
    if actual != expected_sha256:
        raise GateError(f"P25 SHA mismatch; actual={actual}; expected={expected_sha256}; STOP")
    return extract_boot_v2(blob), actual


def verify_host() -> None:
    if os.uname().machine != "aarch64":
        raise GateError("requires aarch64 (C-unit Debian)")
    if os.uname().release != EXPECTED_KERNEL_RELEASE:
        raise GateError(f"kernel ABI differs: {os.uname().release}")
    if "bootslot=a" not in Path("/proc/cmdline").read_text().split():
        raise GateError("not running from bootslot=a")
    if Path("/proc/sys/kernel/kexec_load_disabled").read_text().strip() != "0":
        raise GateError("kexec is disabled")
    kconfig = Path("/proc/config.gz")
    if kconfig.exists():
        conf = gzip.decompress(kconfig.read_bytes()).decode("utf-8")
        if "CONFIG_KEXEC=y" not in conf.splitlines():
            raise GateError("CONFIG_KEXEC=y not found")
    if os.geteuid() != 0:
        raise GateError("requires root")


def stage(args: argparse.Namespace) -> dict:
    if args.destination.exists() and any(args.destination.iterdir()):
        raise GateError("destination must be empty, refusing to overwrite files")
    image, p25_sha = read_and_check_p25(args.p25, args.expected_sha256)
    fdt = read_fdt(args.fdt)
    cmdline = Path("/proc/cmdline").read_text().strip()
    if not cmdline:
        raise GateError("/proc/cmdline empty")
    args.destination.mkdir(parents=True, exist_ok=True, mode=0o700)
    (args.destination / "Image").write_bytes(image)
    (args.destination / "live.dtb").write_bytes(fdt)
    manifest = {
        "schema": 1,
        "status": "STAGED_ONLY_NO_KEXEC_LOAD_OR_EXEC",
        "expected_running_kernel": EXPECTED_KERNEL_RELEASE,
        "p25_device": str(args.p25),
        "p25_sha256": p25_sha,
        "image_sha256": digest(image),
        "image_size": len(image),
        "fdt_sha256": digest(fdt),
        "cmdline": cmdline,
        "note": "Built-in initramfs expected from maker, but runtime boot not yet proven through kexec",
    }
    (args.destination / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    return manifest


def load_stage(destination: Path, binary: str = "kexec") -> list[str]:
    verify_host()
    manifest_path = destination / "manifest.json"
    if not manifest_path.is_file():
        raise GateError("stage manifest missing; run stage first")
    manifest = json.loads(manifest_path.read_text())
    image = (destination / "Image").read_bytes()
    dtb = read_fdt(destination / "live.dtb")
    if digest(image) != manifest.get("image_sha256") or digest(dtb) != manifest.get("fdt_sha256"):
        raise GateError("staged Image/DTB integrity check failed")
    if image[56:60] != b"ARM\x64" or len(image) != manifest.get("image_size"):
        raise GateError("staged Image is malformed")
    if Path("/proc/cmdline").read_text().strip() != manifest.get("cmdline"):
        raise GateError("the running cmdline changed since stage")
    if not shutil.which(binary):
        raise GateError("kexec executable missing; install the Debian kexec-tools package")
    cmd = [binary, "--kexec-syscall", "--load", str(destination / "Image"),
           "--dtb=" + str(destination / "live.dtb"),
           "--append=" + manifest["cmdline"]]
    return cmd


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("action", choices=["inspect", "stage", "load", "unload"])
    ap.add_argument("--p25", type=Path, default=Path("/dev/disk/by-partlabel/boot_a"))
    ap.add_argument("--fdt", type=Path, default=Path("/sys/firmware/fdt"))
    ap.add_argument("--expected-sha256", default=KNOWN_PROVEN_P25_SHA256)
    ap.add_argument("--destination", type=Path, default=Path("/run/terminal6-kexec-g1"))
    args = ap.parse_args()
    try:
        if args.action == "inspect":
            verify_host()
            fdt = read_fdt(args.fdt)
            print(f"HOST_PASS kernel={os.uname().release} FDT_bytes={len(fdt)} FDT_sha256={digest(fdt)}")
            print(f"P25_EXPECTED_SHA256={args.expected_sha256}")
            print(f"P25_PARTITION={args.p25}")
            print("NO_DEVICE_WRITES_NO_KEXEC_LOAD_NO_REBOOT")
        elif args.action == "stage":
            verify_host()
            if not str(args.destination).startswith("/run/"):
                raise GateError("destination must be under /run (tmpfs)")
            result = stage(args)
            print(json.dumps(result, indent=2))
            print("STAGE_PASS: RAM only; no kexec syscall, no reboot")
        elif args.action == "load":
            cmd = load_stage(args.destination)
            print("LOADING_INTO_RAM_ONLY; this will NOT transfer control")
            subprocess.run(cmd, check=True)
            print("KEXEC_LOAD_PASS: loaded but second-stage boot NOT tested; use UART for separately approved kexec -e")
        elif args.action == "unload":
            verify_host()
            if not shutil.which("kexec"):
                raise GateError("kexec executable missing")
            subprocess.run(["kexec", "--unload"], check=True)
            print("KEXEC_UNLOAD_PASS")
        return 0
    except (GateError, OSError, subprocess.CalledProcessError, ValueError, json.JSONDecodeError) as ex:
        print(f"BLOCKED: {ex}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
