#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Negative tests for read-only P44 archive/installed PID1 ABI handoff checks."""
from __future__ import annotations
import hashlib
import importlib.util
import io
from pathlib import Path
import struct
import tarfile
import tempfile
import unittest
import zipfile

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "audit-proto2-p44-pid1.py"
spec = importlib.util.spec_from_file_location("proto2_pid1_audit", SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def fake_elf(interpreter="/lib/ld-linux-aarch64.so.1"):
    buf = bytearray(256)
    buf[:6] = b"\x7fELF\x02\x01"
    struct.pack_into("<H", buf, 18, 183)
    struct.pack_into("<Q", buf, 32, 64)
    struct.pack_into("<H", buf, 54, 56)
    struct.pack_into("<H", buf, 56, 1)
    marker = interpreter.encode() + b"\0"
    struct.pack_into("<I", buf, 64, 3)
    struct.pack_into("<Q", buf, 72, 128)
    struct.pack_into("<Q", buf, 96, len(marker))
    buf[128:128 + len(marker)] = marker
    return bytes(buf)


def fixture(base: Path, *, absolute_loader=False):
    root = base / "p44"
    for name in ("usr/sbin", "usr/lib", "usr/lib/systemd", "usr/lib/aarch64-linux-gnu", "etc"):
        (root / name).mkdir(parents=True, exist_ok=True)
    (root / "sbin").symlink_to("usr/sbin")
    (root / "lib").symlink_to("usr/lib")
    (root / "usr/sbin/init").symlink_to("../lib/systemd/systemd")
    (root / "usr/lib/systemd/systemd").write_bytes(fake_elf())
    (root / "usr/lib/systemd/systemd").chmod(0o755)
    if absolute_loader:
        loader = root / "usr/lib/aarch64-linux-gnu/ld-linux-aarch64.so.1"
    else:
        loader = root / "usr/lib/ld-linux-aarch64.so.1"
    loader.write_bytes(b"\x7fELF\x02\x01\x01")
    loader.chmod(0o755)
    if absolute_loader:
        (root / "usr/lib/ld-linux-aarch64.so.1").symlink_to(
            "/usr/lib/aarch64-linux-gnu/ld-linux-aarch64.so.1")
    tarpath = base / "rootfs.tar.gz"
    with tarfile.open(tarpath, "w:gz", dereference=False) as archive:
        # Do not traverse symlink directories.
        archive.add(root, arcname=".", recursive=True)
    zipfile_path = base / "p44-install.zip"
    with zipfile.ZipFile(zipfile_path, "w") as output:
        output.write(tarpath, "rootfs.tar.gz")
    return root, zipfile_path, hashlib.sha256(zipfile_path.read_bytes()).hexdigest()


class PID1AuditTests(unittest.TestCase):
    def test_archive_and_guest_root_pid1_match(self):
        with tempfile.TemporaryDirectory() as d:
            root, z, sha = fixture(Path(d))
            r = module.verify(z, sha, root, True)
            self.assertEqual(r["installed_P44"], "PID1_AND_INTERPRETER_BYTE_MATCH_PASS")
            self.assertEqual(r["archive"]["init"], "/usr/lib/systemd/systemd")
            self.assertEqual(r["archive"]["interpreter_resolved"], "/usr/lib/ld-linux-aarch64.so.1")

    def test_absolute_guest_symlink_does_not_resolve_host_loader(self):
        with tempfile.TemporaryDirectory() as d:
            root, z, sha = fixture(Path(d), absolute_loader=True)
            r = module.verify(z, sha, root, True)
            self.assertEqual(r["archive"]["interpreter_resolved"],
                             "/usr/lib/aarch64-linux-gnu/ld-linux-aarch64.so.1")
            self.assertEqual(r["installed_P44"], "PID1_AND_INTERPRETER_BYTE_MATCH_PASS")

    def test_rejects_on_disk_systemd_tampering(self):
        with tempfile.TemporaryDirectory() as d:
            root, z, sha = fixture(Path(d))
            with (root / "usr/lib/systemd/systemd").open("ab") as f:
                f.write(b"modified")
            with self.assertRaisesRegex(ValueError, "INSTALLED_PID1_DIFFERS_FROM_ZIP"):
                module.verify(z, sha, root, True)

    def test_rejects_incorrect_zip_sha(self):
        with tempfile.TemporaryDirectory() as d:
            root, z, sha = fixture(Path(d))
            with self.assertRaisesRegex(ValueError, "P44_ZIP_EXACT_SHA_MISMATCH"):
                module.verify(z, "0" * 64, None, False)

    def test_rejects_missing_on_disk_interp(self):
        with tempfile.TemporaryDirectory() as d:
            root, z, sha = fixture(Path(d))
            (root / "usr/lib/ld-linux-aarch64.so.1").unlink()
            with self.assertRaisesRegex(ValueError, "INTERPRETER_NOT_EXECUTABLE"):
                module.verify(z, sha, root, True)

    def test_rejects_bad_init_mode(self):
        with tempfile.TemporaryDirectory() as d:
            root, z, sha = fixture(Path(d))
            (root / "usr/lib/systemd/systemd").chmod(0o644)
            with self.assertRaisesRegex(ValueError, "INIT_NOT_EXECUTABLE"):
                module.verify(z, sha, root, True)

    def test_rejects_symlink_cycle(self):
        with tempfile.TemporaryDirectory() as d:
            root, z, sha = fixture(Path(d))
            (root / "usr/sbin/init").unlink()
            (root / "usr/sbin/init").symlink_to("/sbin/init")
            with self.assertRaisesRegex(ValueError, "P44_SYMLINK_LOOP"):
                module.verify(z, sha, root, True)

    def test_no_execution_and_no_mount_in_source(self):
        source = SCRIPT.read_text()
        self.assertNotIn("subprocess.run(", source)
        self.assertNotIn("os.chroot(", source)
        self.assertIn("P44_MOUNT_MUST_ALREADY_BE_READ_ONLY", source)
        self.assertIn("do not execute", source.lower())


if __name__ == "__main__":
    unittest.main()
