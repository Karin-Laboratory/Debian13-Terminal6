#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Unit tests for public-release boot-v2 header observation; no vendor bytes."""
import hashlib
import importlib.util
from pathlib import Path
import struct
import unittest

p=Path(__file__).resolve().parents[1]/"scripts/derive-public-boot-v2-profile.py"
spec=importlib.util.spec_from_file_location("public_boot",p)
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def fake_reference():
    r=bytearray(m.SIZE)
    r[:8]=b"ANDROID!"
    kernel=b"x"*11
    vals=(len(kernel),0x81000000,0,0x1000000,0,0xF00000,0,2048,2,0x20000)
    struct.pack_into("<10I",r,8,*vals)
    r[48:54]=b"mt6990"
    struct.pack_into("<I",r,1644,1660)
    rawfdt=bytearray(40)
    struct.pack_into(">II",rawfdt,0,0xd00dfeed,40)
    table=(struct.pack(">8I",0xd7b7ab1e,104,32,32,1,32,2048,0)
           +struct.pack(">8I",40,64,0,0,0,0,0,0) +rawfdt)
    struct.pack_into("<I",r,1648,len(table))
    struct.pack_into("<Q",r,1652,0x1F00000)
    r[2048:2048+len(kernel)]=kernel
    r[4096:4096+len(table)]=table
    return bytes(r)


class TestPublicBootProfile(unittest.TestCase):
    def test_valid_observation(self):
        raw=fake_reference()
        d=m.public_profile(raw, hashlib.sha256(raw).hexdigest())
        self.assertEqual(d["dtb_addr"],0x1F00000)
        self.assertEqual(d["kernel_addr"],0x81000000)
        self.assertEqual(d["header_version"],2)
        self.assertIn("rootfs_data",d["cmdline"])
        self.assertNotIn("bootopt",d["cmdline"])

    def test_reject_wrong_digest_and_table(self):
        raw=fake_reference()
        with self.assertRaises(ValueError):
            m.public_profile(raw)
        tampered=bytearray(raw)
        tampered[4096]=0
        with self.assertRaisesRegex(ValueError,"DT-table"):
            m.public_profile(bytes(tampered),hashlib.sha256(tampered).hexdigest())

    def test_reference_requires_full_exact_image(self):
        with self.assertRaises(ValueError):
            m.public_profile(b"ANDROID!")

    def test_reference_sha_is_published_value(self):
        self.assertEqual(m.RC16_SHA256,"4ee38fb3f85c7980889c5fe08f78a111069b485c9f7b8a13f09913430fa89787")


if __name__=="__main__":
    unittest.main()
