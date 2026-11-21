#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Strict proto2 P44 candidate pairing, no signed P25 image in ZIP."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import zipfile
import tarfile


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


P25_SIGNED_SHA = "74c1c98b31cdba54f71d16f1983fbeff347bb334c5ae7d7f1353cd57f734936e"
KERNEL = "6.18.63-debian-t6-proto2"
MODULE_SHAS = {
    "mt76.ko": "26ffb6bd648a8fa91b424bbcf890710f8695d679d45b372e2e7ba05b68449c2f",
    "mt76-connac-lib.ko": "9f2df583cc73c738f7a186f1ef16faffcb6919bdf915f4ec9cf09a3df1fa05a6",
    "mt7996e.ko": "c87f66f6573d5a4c3d1e829009fc42baf3223f1b0b958c4fc8a549b135e0fecd",
}

def verify_modules_tar(path: Path):
    prefix = f"lib/modules/{KERNEL}/updates/terminal6-mt76/"
    seen = set()
    with tarfile.open(path, "r:") as tar:
        for entry in tar:
            name = entry.name.removeprefix("./")
            if entry.isdir():
                continue
            if not entry.isfile() or not name.startswith(prefix):
                raise ValueError("unexpected modules tar entry: " + name)
            filename = name[len(prefix):]
            if filename == "SHA256SUMS":
                continue
            if filename not in MODULE_SHAS or filename in seen:
                raise ValueError("unapproved module or duplicate: " + filename)
            stream = tar.extractfile(entry)
            if stream is None:
                raise ValueError("empty module stream")
            if hashlib.sha256(stream.read()).hexdigest() != MODULE_SHAS[filename]:
                raise ValueError("module SHA mismatch: " + filename)
            seen.add(filename)
    if seen != set(MODULE_SHAS):
        raise ValueError("incomplete 3-module proto2 set")


def verify_owner_neutral_rootfs(path: Path):
    """Check the actual tar archive, not merely builder source code."""
    required = {
        "etc/systemd/system/terminal6-firstboot.service",
        "etc/systemd/system/terminal6-authcheck.service",
        "etc/ssh/sshd_config.d/60-terminal6-secure.conf",
        "etc/systemd/system/ssh.service.d/10-terminal6-provisioned.conf",
        "etc/modprobe.d/terminal6-proto2-wifi.conf",
        "usr/local/sbin/terminal6-proto2-wifi-start",
        "usr/local/sbin/terminal6-p44-firstboot",
    }
    found = set()
    with tarfile.open(path, "r:gz") as tar:
        for entry in tar:
            name = entry.name.removeprefix("./")
            if name.startswith("/") or ".." in name.split("/"):
                raise ValueError("unsafe path in rootfs tar")
            if name.startswith("root/.ssh/") or name.startswith("etc/dropbear/dropbear_"):
                raise ValueError("owner credential or host key in rootfs")
            if name.startswith("etc/ssh/ssh_host_"):
                raise ValueError("shared SSH host identity in rootfs")
            if name in {"var/lib/terminal6/firstboot-complete",
                        "var/lib/terminal6/firstboot-auth-verified"}:
                raise ValueError("preprovisioned firstboot marker")
            if name.startswith("lib/firmware/mediatek/mt7996/") and "eeprom" in name.lower():
                raise ValueError("embedded device calibration data")
            if name == "etc/machine-id" and (not entry.isfile() or entry.size):
                raise ValueError("shared machine-id")
            if name == "etc/shadow":
                if not entry.isfile():
                    raise ValueError("invalid root shadow")
                stream = tar.extractfile(entry)
                if stream is None:
                    raise ValueError("unreadable root shadow")
                roots = [line for line in stream.read().decode().splitlines()
                         if line.startswith("root:")]
                if len(roots) != 1 or roots[0].split(":")[1] != "":
                    raise ValueError("root must have no preset password")
            if name in required:
                found.add(name)
    missing = required - found
    if missing:
        raise ValueError("missing portable P44 firstboot/wifi entries: " + repr(sorted(missing)))

def package(rootfs: Path, modules: Path, p25: Path, kernel_release: Path, output: Path, source: str):
    for name, path in (("rootfs", rootfs), ("modules", modules), ("p25", p25), ("release", kernel_release)):
        if not path.is_file() or not path.stat().st_size:
            raise ValueError("missing required artifact: " + name)
    if p25.stat().st_size != 33554432:
        raise ValueError("P25 MUST be exactly 32 MiB")
    if digest(p25) != P25_SIGNED_SHA:
        raise ValueError("SIGNED P25 hash differs from C-unit boot-proven SHA")
    verify_modules_tar(modules)
    verify_owner_neutral_rootfs(rootfs)
    if not re.fullmatch(r"[0-9a-f]{40}", source):
        raise ValueError("source must be exact 40-char commit ID")
    if output.exists():
        raise ValueError("refuse overwrite " + str(output))
    release = kernel_release.read_text().strip()
    if release != KERNEL or "\n" in release:
        raise ValueError("invalid kernel.release")
    inputs = {"rootfs.tar.gz": rootfs, "modules.tar": modules}
    items = {name: {"sha256": digest(file), "bytes": file.stat().st_size}
             for name, file in inputs.items()}
    manifest = {
        "schema": "cunit-p44-install-v1",
        "installation_method": "B_MANUAL_EXTERNAL_PREBOOT_NO_INSTALLER",
        "charter_version": "1.4",
        "status": "PROTO2_P44_CANDIDATE_HARDWARE_NOT_TESTED_NO_PUBLIC_BINARY_RIGHTS",
        "source_commit": source,
        "kernel_release": release,
        "p25_signed_boot_tested": {"sha256": digest(p25), "bytes": p25.stat().st_size},
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
    # Manual Method B requires no special installer; include a human-readable
    # inspection and extraction guide within the delivery container.
    manual = (Path(__file__).resolve().parents[1] / "docs/CUNIT-P44-PROTO2-PORTABLE-RUNBOOK.ja.md").read_bytes()
    contents = {
        "MANUAL-INSTALL.ja.md": manual,
        "manifest.json": manifest_bytes,
        "SHA256SUMS": sums,
        "kernel.release": (release + "\n").encode(),
        "INSTALL-STATUS.txt": b"PROTO2 P44 CANDIDATE NOT HARDWARE ACCEPTED; no public binary rights confirmed.\n",
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
    print("PAIR_P25_SHA256", manifest["p25_signed_boot_tested"]["sha256"])


def main():
    p = argparse.ArgumentParser()
    for name in ("rootfs", "modules", "p25", "kernel_release", "output", "source"):
        p.add_argument("--" + name.replace("_", "-"), required=True)
    args = p.parse_args()
    package(Path(args.rootfs), Path(args.modules), Path(args.p25),
            Path(args.kernel_release), Path(args.output), args.source)


if __name__ == "__main__":
    main()
