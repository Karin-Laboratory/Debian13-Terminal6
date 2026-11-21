#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""No device or private binaries required: offline stage unit tests."""
import importlib.util
import hashlib
import json
from pathlib import Path
import struct
import tempfile
import unittest
import zipfile

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/stage-v10-debian-kexec-offline.py"
spec = importlib.util.spec_from_file_location("v10_stage", SCRIPT)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

class OfflineStageTests(unittest.TestCase):
    def test_arm64_image_magic(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "Image"
            p.write_bytes(bytes(56) + b"ARMd")
            self.assertEqual(m.verify_arm64_image(p), 60)
            p.write_bytes(bytes(64))
            with self.assertRaises(ValueError):
                m.verify_arm64_image(p)

    def test_dtb_magic_and_bounds(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "board.dtb"
            p.write_bytes(struct.pack(">II", 0xd00dfeed, 40) + bytes(32))
            self.assertEqual(m.verify_dtb(p), 40)
            p.write_bytes(struct.pack(">II", 0xd00dfeed, 41) + bytes(32))
            with self.assertRaises(ValueError):
                m.verify_dtb(p)

    def test_archive_paths(self):
        for unsafe in ("../passwd", "/absolute", "a/../b", "a\\b", ""):
            with self.assertRaises(ValueError):
                m.validate_path(unsafe)

    def test_p44_bad_sha_fails_before_opening(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "P44-install.zip"
            with zipfile.ZipFile(p, "w") as z:
                z.writestr("manifest.json", "{}")
            with self.assertRaisesRegex(ValueError, "differs"):
                m.verify_p44(p)

if __name__ == "__main__":
    unittest.main()
