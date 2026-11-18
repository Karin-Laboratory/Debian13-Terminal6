#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Reproducible owner-neutral P44-install.zip (candidate, unsigned P25 pairing)."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import zipfile


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def package(rootfs: Path, modules: Path, p25: Path, kernel_release: Path, output: Path, source: str):
    for name, path in (("rootfs", rootfs), ("modules", modules), ("p25", p25), ("release", kernel_release)):
        if not path.is_file() or not path.stat().st_size:
            raise ValueError("missing required artifact: " + name)
    if p25.stat().st_size != 33554432:
        raise ValueError("P25 MUST be exactly 32 MiB")
    if not re.fullmatch(r"[0-9a-f]{40}", source):
        raise ValueError("source must be exact 40-char commit ID")
    if output.exists():
        raise ValueError("refuse overwrite " + str(output))
    release = kernel_release.read_text().strip()
    if not release or "\n" in release:
        raise ValueError("invalid kernel.release")
    inputs = {"rootfs.tar.gz": rootfs, "modules.tar": modules}
    items = {name: {"sha256": digest(file), "bytes": file.stat().st_size}
             for name, file in inputs.items()}
    manifest = {
        "schema": "cunit-p44-install-v1",
        "charter_version": "1.2",
        "status": "EXPERIMENTAL_UNSIGNED_P25_NO_HARDWARE_ACCEPTANCE",
        "source_commit": source,
        "kernel_release": release,
        "p25_unsigned": {"sha256": digest(p25), "bytes": p25.stat().st_size},
        "files": items,
        "install_constraints": {
            "requires_empty_ext4_p44": True,
            "requires_physical_isolated_lan": True,
            "preserve_existing_data": True,
            "host_keys_generated_per_device": True,
            "empty_password_must_never_remain_after_setup": True,
        },
    }
    manifest_bytes = (json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode()
    sums = "".join(f"{items[name]['sha256']}  {name}\n" for name in sorted(inputs)).encode()
    contents = {
        "manifest.json": manifest_bytes,
        "SHA256SUMS": sums,
        "kernel.release": (release + "\n").encode(),
        "INSTALL-STATUS.txt": b"NOT SIGNED, NOT HARDWARE ACCEPTED. Install only on VERIFIED EMPTY P44.\n",
    }
    with zipfile.ZipFile(output, "x", compression=zipfile.ZIP_STORED, allowZip64=True) as z:
        for name in sorted(contents):
            info = zipfile.ZipInfo(name, (2026, 11, 18, 0, 0, 0))
            info.external_attr = 0o100644 << 16
            info.compress_type = zipfile.ZIP_STORED
            z.writestr(info, contents[name])
        for name in sorted(inputs):
            info = zipfile.ZipInfo(name, (2026, 11, 18, 0, 0, 0))
            info.external_attr = 0o100644 << 16
            info.compress_type = zipfile.ZIP_STORED
            with z.open(info, "w", force_zip64=True) as dest, inputs[name].open("rb") as src:
                for block in iter(lambda: src.read(1024 * 1024), b""):
                    dest.write(block)
    with zipfile.ZipFile(output, "r") as z:
        if z.testzip() is not None:
            raise ValueError("ZIP CRC fail")
        decoded = json.loads(z.read("manifest.json"))
        if decoded != manifest:
            raise ValueError("ZIP manifest mismatch")
        for name in inputs:
            h = hashlib.sha256(z.read(name)).hexdigest()
            if h != items[name]["sha256"]:
                raise ValueError("ZIP internal SHA mismatch")
    print("CUNIT_P44_INSTALL_ZIP_PACKED_AND_INDEPENDENTLY_REOPENED")
    print("P44_INSTALL_ZIP_BYTES", output.stat().st_size)
    print("P44_INSTALL_ZIP_SHA256", digest(output))
    print("PAIR_P25_SHA256", manifest["p25_unsigned"]["sha256"])


def main():
    p = argparse.ArgumentParser()
    for name in ("rootfs", "modules", "p25", "kernel_release", "output", "source"):
        p.add_argument("--" + name.replace("_", "-"), required=True)
    args = p.parse_args()
    package(Path(args.rootfs), Path(args.modules), Path(args.p25),
            Path(args.kernel_release), Path(args.output), args.source)


if __name__ == "__main__":
    main()
