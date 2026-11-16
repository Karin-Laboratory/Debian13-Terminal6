#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Offline checks for template-free unsigned engineering P25 input validation."""
import importlib.util
from pathlib import Path
import unittest

P = Path(__file__).resolve().parents[1] / "scripts/assemble-template-free-p25.py"
s = importlib.util.spec_from_file_location("template_free_p25", P)
m = importlib.util.module_from_spec(s)
s.loader.exec_module(m)


def profile():
    return {"header_version": 2, "header_size": 1660, "page_size": 2048,
            "kernel_addr": 0, "ramdisk_addr": 0x1000000,
            "second_addr": 0xF00000, "tags_addr": 0, "dtb_addr": 0x1F00000,
            "os_version": 0, "name": "mt6990", "cmdline": "root=PARTLABEL=rootfs_data"}


class TestTemplateFreeP25(unittest.TestCase):
    def test_profile_schema(self):
        m.check_meta(profile())

    def test_reject_invented_board_settings(self):
        d = profile()
        d["header_version"] = 3
        with self.assertRaises(ValueError):
            m.check_meta(d)
        d = profile()
        d["kernel_addr"] = -1
        with self.assertRaises(ValueError):
            m.check_meta(d)
        d = profile()
        d["dtb_addr"] = True
        with self.assertRaises(ValueError):
            m.check_meta(d)

    def test_reject_unbounded_or_implicit_profile(self):
        d = profile()
        d["name"] = "x" * 16
        with self.assertRaises(ValueError):
            m.check_meta(d)
        d = profile()
        d["private_template"] = "something"
        with self.assertRaises(ValueError):
            m.check_meta(d)

    def test_reject_invalid_header(self):
        with self.assertRaises(ValueError):
            m.verify_image(b"bad", b"not-image", b"DTB", profile())

    def test_blob_lock(self):
        self.assertEqual(len(m.PACKER_BLOB), 40)
        self.assertEqual(m.git_blob_sha(b""), "e69de29bb2d1d6434b8b29ae775ad8c2e48c5391")


if __name__ == "__main__":
    unittest.main()
