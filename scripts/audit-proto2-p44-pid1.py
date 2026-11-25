#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Read-only comparison of an owner-approved proto2 P44 ZIP and mounted P44.

Does not mount, fsck, chroot, execute /sbin/init, install or alter files.
For the actual device, mount P44 separately with ro,noload (after explicit
authorization), then pass --root <mountpoint>. This script requires that
mountpoint to be a read-only filesystem, unless --offline-test-root is used.

Checks only the PID1 execution chain, not every P44 file or runtime systemd.
All paths are resolved relative to the *guest* P44 root; absolute symlinks
must never escape to the host's /lib, /sbin or /usr.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import posixpath
import stat
import struct
import sys
import tarfile
import zipfile

CUNIT_ZIP = "57058163645c0acfe7b9f5f760d7a2dc8af78fca33a81604a8d37d23c5815d3b"
SENSITIVE = (
    "/sbin/init",
    "/usr/lib/systemd/systemd",
    "/lib/ld-linux-aarch64.so.1",
    "/usr/lib/aarch64-linux-gnu/libc.so.6",
)
MAX_DEPTH = 60


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for part in iter(lambda: stream.read(1 << 20), b""):
            h.update(part)
    return h.hexdigest()


def normalized(name: str) -> str:
    parts = []
    for seg in name.replace("\\", "/").split("/"):
        if seg in ("", "."):
            continue
        if seg == "..":
            if not parts:
                raise ValueError("P44_PATH_ESCAPE")
            parts.pop()
        else:
            parts.append(seg)
    return "/".join(parts)


def tar_catalog(zippath: Path) -> dict:
    # Inspect ZIP as a container only. Never extract its entries to the host.
    catalog = {"": {"type": "dir", "mode": 0o755}}
    with zipfile.ZipFile(zippath) as z:
        names = z.namelist()
        if len(names) != len(set(names)) or "rootfs.tar.gz" not in names:
            raise ValueError("P44_ZIP_MISSING_OR_DUPLICATE_ROOTFS")
        with z.open("rootfs.tar.gz") as file:
            with tarfile.open(fileobj=file, mode="r|gz") as archive:
                for member in archive:
                    name = normalized(member.name)
                    if not name:
                        continue
                    if name in catalog:
                        raise ValueError("P44_DUPLICATE_TAR_ENTRY:" + name)
                    mode = member.mode & 0o7777
                    if member.isdir():
                        kind = "dir"
                    elif member.issym():
                        kind = "link"
                    elif member.isreg():
                        kind = "file"
                    else:
                        # A normal Debian rootfs may include character devices or
                        # FIFOs, but none may be used as a PID1/loader file.
                        kind = "other"
                    row = {"type": kind, "mode": mode, "uid": member.uid, "gid": member.gid}
                    if kind == "link":
                        row["target"] = member.linkname
                    if kind == "file" and _interesting(name):
                        body = archive.extractfile(member)
                        if body is None:
                            raise ValueError("P44_CANNOT_READ_ARCHIVE_ENTRY:" + name)
                        row["sha256"] = hashlib.sha256(body.read()).hexdigest()
                    catalog[name] = row
    return catalog


def _interesting(name: str) -> bool:
    leaf = name.split("/")[-1]
    return (leaf in {"systemd", "ld-linux-aarch64.so.1", "libc.so.6"}
            or leaf.startswith("libsystemd-shared-") and leaf.endswith(".so"))


def root_entry(root: Path, name: str) -> dict | None:
    file = root / name
    try:
        st = file.lstat()
    except FileNotFoundError:
        return None
    if stat.S_ISLNK(st.st_mode):
        return {"type": "link", "target": os.readlink(file),
                "mode": stat.S_IMODE(st.st_mode), "uid": st.st_uid, "gid": st.st_gid}
    if stat.S_ISDIR(st.st_mode):
        kind = "dir"
    elif stat.S_ISREG(st.st_mode):
        kind = "file"
    else:
        kind = "other"
    row = {"type": kind, "mode": stat.S_IMODE(st.st_mode),
           "uid": st.st_uid, "gid": st.st_gid}
    if kind == "file" and _interesting(name):
        row["sha256"] = digest(file)
    return row


def resolved(get_entry, absolute: str):
    """Resolve each symlink component as if rooted in Debian P44, not host."""
    remaining = absolute.strip("/").split("/")
    prefix = []
    trace = []
    for _ in range(MAX_DEPTH):
        if not remaining or remaining == [""]:
            name = "/".join(prefix)
            return name, get_entry(name), trace
        component = remaining.pop(0)
        if component in ("", "."):
            continue
        if component == "..":
            if not prefix:
                raise ValueError("P44_LINK_ESCAPES_ROOT")
            prefix.pop()
            continue
        candidate = "/".join(prefix + [component])
        meta = get_entry(candidate)
        if meta is None:
            return candidate, None, trace
        if meta["type"] == "link":
            target = meta["target"]
            trace.append({"path": candidate, "target": target})
            destination = target if target.startswith("/") else posixpath.join("/" + "/".join(prefix), target)
            # Normalize guest path. Never use host os.path.realpath here.
            normalized_dest = normalized(destination)
            prefix = []
            remaining = normalized_dest.split("/") + remaining
        else:
            if remaining and meta["type"] != "dir":
                raise ValueError("P44_NON_DIRECTORY_ANCESTOR:" + candidate)
            prefix.append(component)
    raise ValueError("P44_SYMLINK_LOOP_OR_EXCESSIVE_DEPTH")


def interpreter_from_elf(binary: bytes) -> str:
    if len(binary) < 64 or binary[:6] != b"\x7fELF\x02\x01":
        raise ValueError("P44_INIT_NOT_ELF64_LE")
    if struct.unpack_from("<H", binary, 18)[0] != 183:
        raise ValueError("P44_INIT_NOT_AARCH64")
    off = struct.unpack_from("<Q", binary, 32)[0]
    width = struct.unpack_from("<H", binary, 54)[0]
    count = struct.unpack_from("<H", binary, 56)[0]
    if width < 56 or width > 256 or count > 128 or off + width * count > len(binary):
        raise ValueError("P44_INIT_ELF_PROGRAM_HEADERS_INVALID")
    for i in range(count):
        ent = off + i * width
        if struct.unpack_from("<I", binary, ent)[0] == 3:
            pos, size = struct.unpack_from("<Q", binary, ent + 8)[0], struct.unpack_from("<Q", binary, ent + 32)[0]
            if not (1 <= size <= 512 and pos + size <= len(binary)):
                raise ValueError("P44_INIT_PT_INTERP_INVALID")
            value = binary[pos:pos+size].rstrip(b"\0").decode("ascii")
            if not value.startswith("/"):
                raise ValueError("P44_INIT_INTERPRETER_NOT_ABSOLUTE")
            return value
    raise ValueError("P44_INIT_PT_INTERP_MISSING")


def validate_chain(get_entry, read_systemd, label: str):
    init_path, init, init_trace = resolved(get_entry, "/sbin/init")
    if init is None or init["type"] != "file" or not (init["mode"] & 0o111):
        raise ValueError(label + "_INIT_NOT_EXECUTABLE")
    if init_path != "usr/lib/systemd/systemd":
        raise ValueError(label + "_INIT_WRONG_TARGET:" + init_path)
    interp = interpreter_from_elf(read_systemd())
    interp_path, loader, loader_trace = resolved(get_entry, interp)
    if loader is None or loader["type"] != "file" or not (loader["mode"] & 0o111):
        raise ValueError(label + "_INTERPRETER_NOT_EXECUTABLE")
    return {
        "init": "/" + init_path, "init_chain": init_trace,
        "init_sha256": init.get("sha256"),
        "interpreter": interp, "interpreter_resolved": "/" + interp_path,
        "interpreter_chain": loader_trace,
        "interpreter_sha256": loader.get("sha256"),
    }


def archive_systemd_bytes(zippath: Path) -> bytes:
    with zipfile.ZipFile(zippath) as z:
        with z.open("rootfs.tar.gz") as file:
            with tarfile.open(fileobj=file, mode="r|gz") as t:
                for member in t:
                    if normalized(member.name) == "usr/lib/systemd/systemd" and member.isfile():
                        stream = t.extractfile(member)
                        if stream:
                            return stream.read()
    raise ValueError("P44_ARCHIVE_SYSTEMD_MISSING")


def verify(zippath: Path, expected_sha: str, root: Path | None, offline_test_root: bool):
    if not zippath.is_file() or zippath.is_symlink() or digest(zippath) != expected_sha:
        raise ValueError("P44_ZIP_EXACT_SHA_MISMATCH")
    cat = tar_catalog(zippath)
    get_tar = lambda name: cat.get(name)
    archive = validate_chain(get_tar, lambda: archive_systemd_bytes(zippath), "ARCHIVE")
    result = {"status": "P44_ZIP_PID1_STATIC_PASS",
              "zip_sha256": expected_sha,
              "archive": archive,
              "installed_P44": "NOT_TESTED"}
    if root is None:
        return result
    if not root.is_dir() or root.is_symlink():
        raise ValueError("P44_ROOT_NOT_DIRECTORY")
    if not offline_test_root:
        if not os.path.ismount(root) or not (os.statvfs(root).f_flag & os.ST_RDONLY):
            raise ValueError("P44_MOUNT_MUST_ALREADY_BE_READ_ONLY")
    get_disk = lambda name: root_entry(root, name)
    # Do not execute target P44's /sbin/init or use host dynamic loader.
    systemd_path, systemd_meta, _ = resolved(get_disk, "/usr/lib/systemd/systemd")
    if not systemd_meta or systemd_meta["type"] != "file":
        raise ValueError("INSTALLED_SYSTEMD_MISSING")
    installed = validate_chain(get_disk, lambda: (root / systemd_path).read_bytes(), "INSTALLED")
    if (installed["init"] != archive["init"]
        or installed["interpreter"] != archive["interpreter"]
        or installed["interpreter_resolved"] != archive["interpreter_resolved"]
        or installed["init_sha256"] != archive["init_sha256"]
        or installed["interpreter_sha256"] != archive["interpreter_sha256"]):
        raise ValueError("INSTALLED_PID1_DIFFERS_FROM_ZIP")
    # Ensure loader and init modes are executable. read-only stat already checked.
    result["installed_P44"] = "PID1_AND_INTERPRETER_BYTE_MATCH_PASS"
    result["installed"] = installed
    result["limitation"] = "Does not verify PID1 systemd runtime, every DT_NEEDED DSO, ACL, FDT, or P25 mount/exec handoff"
    return result


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--zip", required=True, type=Path)
    ap.add_argument("--sha256", default=CUNIT_ZIP)
    ap.add_argument("--root", type=Path)
    ap.add_argument("--offline-test-root", action="store_true",
                    help="only for ephemeral, disposable, non-device test rootfs")
    args = ap.parse_args()
    if args.offline_test_root and args.root is None:
        ap.error("--offline-test-root requires --root")
    try:
        result = verify(args.zip, args.sha256, args.root, args.offline_test_root)
    except (ValueError, OSError, tarfile.TarError, zipfile.BadZipFile) as error:
        print("P44_PID1_PREFLIGHT_FAIL", str(error), file=sys.stderr)
        return 2
    print(json.dumps(result, sort_keys=True, ensure_ascii=False, indent=2))
    print("P44_PID1_AUDIT_PASS_WITH_STATED_LIMITATIONS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
