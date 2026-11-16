#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Offline tests for the source-only, exact-blob public donor acquisition."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "stage-public-mt6990-sources.py"
spec = importlib.util.spec_from_file_location("mt6990_stager", SCRIPT)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

TEXT = b"// SPDX-License-Identifier: GPL-2.0\nint clock_driver;\n"


def fixture():
    return {
        "schema": 1,
        "donor": "13179415360/openwrt-mt6990-lg6851f",
        "revision": "a40df9a5afb46716dea799acea69f17480df4d82",
        "files": [{
            "source": "target/linux/mediatek/files-6.18/drivers/clk/mediatek/clk-mt6990.c",
            "destination": "kernel/drivers/clk/mediatek/clk-mt6990.c",
            "git_blob_sha1": mod.git_blob_sha1(TEXT),
        }],
    }


class TestPublicSourceStaging(unittest.TestCase):
    def test_known_git_blob(self):
        self.assertEqual(mod.git_blob_sha1(b""), "e69de29bb2d1d6434b8b29ae775ad8c2e48c5391")

    def test_success_and_receipt(self):
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp) / "new"
            receipt = mod.stage(fixture(), out, lambda _url: TEXT)
            self.assertEqual(len(receipt["files"]), 1)
            self.assertIn("NOT_BOOT_VALIDATED", receipt["status"])
            self.assertEqual((out / fixture()["files"][0]["destination"]).read_bytes(), TEXT)
            self.assertEqual(json.loads((out / "source-receipt.json").read_text()), receipt)

    def test_wrong_blob_fails_closed_no_output(self):
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp) / "new"
            with self.assertRaisesRegex(ValueError, "mismatch"):
                mod.stage(fixture(), out, lambda _url: b"changed")
            self.assertFalse(out.exists())

    def test_oversize_and_binary_refused(self):
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp) / "new"
            with self.assertRaisesRegex(ValueError, "oversize"):
                mod.stage(fixture(), out, lambda _url: b"x" * (mod.MAX_BLOB + 1))
            self.assertFalse(out.exists())
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp) / "new"
            with self.assertRaises(UnicodeDecodeError):
                mod.stage(fixture(), out, lambda _url: b"\xff")
            self.assertFalse(out.exists())

    def test_path_traversal_and_duplicate_rejected(self):
        d = fixture()
        d["files"][0]["destination"] = "kernel/../secrets.txt"
        with self.assertRaises(ValueError):
            mod.check_manifest(d)
        d = fixture()
        d["files"].append(dict(d["files"][0]))
        with self.assertRaisesRegex(ValueError, "duplicate"):
            mod.check_manifest(d)

    def test_firmware_and_unknown_donor_rejected(self):
        d = fixture()
        d["files"][0]["source"] = "target/linux/mediatek/files-6.18/firmware/secret.bin"
        with self.assertRaises(ValueError):
            mod.check_manifest(d)
        d = fixture()
        d["donor"] = "other/repository"
        with self.assertRaises(ValueError):
            mod.check_manifest(d)

    def test_does_not_overwrite_or_follow_symlink(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            out = base / "new"
            out.mkdir()
            with self.assertRaisesRegex(ValueError, "exists"):
                mod.stage(fixture(), out, lambda _url: TEXT)
            link = base / "link"
            link.symlink_to(base, target_is_directory=True)
            with self.assertRaises(ValueError):
                mod.stage(fixture(), link / "new", lambda _url: TEXT)

    def test_manifest_real_paths_are_pinned_and_safe(self):
        manifest = json.loads((SCRIPT.parent.parent / "configs/public-mt6990-sources.json").read_text())
        files = mod.check_manifest(manifest)
        self.assertGreaterEqual(len(files), 12)
        self.assertTrue(all(f["destination"].startswith(("kernel/", "patches/")) for f in files))


if __name__ == "__main__":
    unittest.main()
