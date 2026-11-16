#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Offline checks for template-free unsigned engineering P25 input validation."""
import importlib.util
from pathlib import Path
import unittest
import struct
import hashlib

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

    def test_public_aosp_dt_table_prefix_matches_observed_reference_sha(self):
        # The expected hash is a published observation of the RC16 standard
        # 64-byte table; test does NOT embed OEM bytes or a private template.
        fdt=bytearray(148765)
        struct.pack_into(">II", fdt, 0, 0xd00dfeed, len(fdt))
        table=m.aosp_dtb_table(bytes(fdt))
        m.validate_aosp_dtb_table(table, bytes(fdt))
        self.assertEqual(len(table), 148829)
        self.assertEqual(
            hashlib.sha256(table[:64]).hexdigest(),
            "f170c43553f75b65bb0f88714f776773f79489cad8725078ddc84bf7fb2d73d2")
        self.assertEqual(struct.unpack_from(">I", table, 32)[0], len(fdt))

    def test_aosp_table_rebuilds_sizes_without_stale_prefix(self):
        def fdt_of_size(n):
            buf=bytearray(n)
            struct.pack_into(">II", buf, 0, 0xd00dfeed, n)
            return bytes(buf)
        first=m.aosp_dtb_table(fdt_of_size(148765))
        new=m.aosp_dtb_table(fdt_of_size(177286))
        self.assertNotEqual(first[:64], new[:64])
        self.assertEqual(struct.unpack_from(">I", new, 4)[0], 177350)
        self.assertEqual(struct.unpack_from(">I", new, 32)[0], 177286)
        m.validate_aosp_dtb_table(new, fdt_of_size(177286))
        with self.assertRaises(ValueError):
            m.validate_aosp_dtb_table(first[:64]+fdt_of_size(177286), fdt_of_size(177286))

    def test_aosp_table_rejects_bad_fdt_size(self):
        fdt=bytearray(44)
        struct.pack_into(">II", fdt, 0, 0xd00dfeed, 40)
        with self.assertRaises(ValueError):
            m.aosp_dtb_table(bytes(fdt))

    def test_blob_lock(self):
        self.assertEqual(len(m.PACKER_BLOB), 40)
        self.assertEqual(m.git_blob_sha(b""), "e69de29bb2d1d6434b8b29ae775ad8c2e48c5391")


if __name__ == "__main__":
    unittest.main()
