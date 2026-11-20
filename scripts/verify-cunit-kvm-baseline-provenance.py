#!/usr/bin/env python3
"""Fail-closed evidence gate before deriving C-unit Wi-Fi P25/P44 from a known-good boot pair.

This checks evidence only. It does not build, sign, flash, mount or modify any input.
Receipt schema:
{
  "baseline_signed_p25": {"path": "...", "sha256": "..."},
  "baseline_kernel": {
    "image": {"path": "...", "sha256": "..."},
    "config": {"path": "...", "sha256": "..."},
    "module_symvers": {"path": "...", "sha256": "..."},
    "system_map": {"path": "...", "sha256": "..."},
    "dtb": {"path": "...", "sha256": "..."},
    "initramfs": {"path": "...", "sha256": "..."},
    "kernel_release": {"path": "...", "sha256": "..."},
    "source_revision": "...",
    "toolchain": "...",
    "patch_manifest": {"path": "...", "sha256": "..."}
  },
  "baseline_p44": {"path": "...", "sha256": "..."}
}
File paths may be relative to the receipt directory. All hashes must come from
independently verified source artifacts, not guessed from historic documents.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

EXPECTED_P25 = "d8005468d4cb0b854d1b25e4abc9543bb5fb2348b7020eb70fe1febaea82a3a4"
EXPECTED_P44 = "9c49552566dc882529142b37deadac2dd2603c8d032933f18a7c917808404bfe"
EXPECTED_KERNEL_RELEASE = "6.18.63-debian-t6-proto2"
FILES = ("image", "config", "module_symvers", "system_map", "dtb",
         "initramfs", "kernel_release", "patch_manifest")


def ensure_file(root, record, label):
    if not isinstance(record, dict) or set(record) != {"path", "sha256"}:
        raise ValueError(f"{label}: requires path and sha256")
    digest = record["sha256"]
    if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
        raise ValueError(f"{label}: invalid sha256")
    candidate = Path(record["path"])
    path = candidate if candidate.is_absolute() else root / candidate
    if not path.is_file() or path.is_symlink():
        raise ValueError(f"{label}: missing/non-regular/symlink file: {path}")
    h = hashlib.sha256()
    with path.open("rb") as file:
        for block in iter(lambda: file.read(4 * 1024 * 1024), b""):
            h.update(block)
    if h.hexdigest() != digest:
        raise ValueError(f"{label}: SHA mismatch")
    return path


def check(receipt):
    obj = json.loads(receipt.read_text(encoding="utf-8"))
    if not isinstance(obj, dict) or set(obj) != {
        "baseline_signed_p25", "baseline_kernel", "baseline_p44"
    }:
        raise ValueError("receipt must contain exactly the 3 required top-level keys")
    p25, p44 = obj["baseline_signed_p25"], obj["baseline_p44"]
    if p25.get("sha256") != EXPECTED_P25:
        raise ValueError("wrong signed P25 baseline; never substitute public-capable")
    if p44.get("sha256") != EXPECTED_P44:
        raise ValueError("wrong restored P44 reference")
    kernel = obj["baseline_kernel"]
    if not isinstance(kernel, dict) or set(kernel) != set(FILES) | {
        "source_revision", "toolchain"
    }:
        raise ValueError("incomplete kernel provenance")
    for name in ("source_revision", "toolchain"):
        if not isinstance(kernel[name], str) or not kernel[name].strip():
            raise ValueError(f"missing {name}")
    root = receipt.parent
    p25_path = ensure_file(root, p25, "baseline signed P25")
    if p25_path.stat().st_size != 33554432:
        raise ValueError("signed P25 must be exactly 32 MiB")
    p44_path = ensure_file(root, p44, "baseline P44")
    if p44_path.stat().st_size != 2684321792:
        raise ValueError("P44 baseline size differs from restoration receipt")
    paths = {name: ensure_file(root, kernel[name], name) for name in FILES}
    if paths["kernel_release"].read_text().strip() != EXPECTED_KERNEL_RELEASE:
        raise ValueError("baseline kernel.release is not proto2")
    print("CUNIT_KVM_BASELINE_PROVENANCE_FILES_AND_SHA_PASS")
    print("NEXT_GATE: reproduce baseline Image and ABI from exact source/toolchain")
    print("NOT_A_BUILD_NOT_A_WIFI_P25_NOT_HARDWARE_ACCEPTANCE")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("receipt", type=Path)
    args = parser.parse_args()
    try:
        check(args.receipt.resolve(strict=True))
    except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
        print(f"CUNIT_KVM_BASELINE_GATE_BLOCKED: {exc}", file=sys.stderr)
        sys.exit(1)
