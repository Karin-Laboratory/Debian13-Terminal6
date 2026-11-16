#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Regression: independently verify a real-size (>16MiB compressed) synthetic P25."""
import gzip
import hashlib
import importlib.util
from pathlib import Path
import struct
import unittest

P=Path(__file__).resolve().parents[1]/"scripts/verify-public-unsigned-p25.py"
spec=importlib.util.spec_from_file_location("independent_p25_validator_large",P)
v=importlib.util.module_from_spec(spec)
spec.loader.exec_module(v)


class TestLargeBootV2(unittest.TestCase):
    def test_52mb_source_17mb_gzip_inside_32mb_partition(self):
        # Match proven public network-build geometry, but use only deterministic
        # synthetic bits, no proprietary firmware, real boot image or signer.
        raw=bytearray(52*1024*1024)
        raw[56:60]=b"ARM\x64"
        fake_cpio=gzip.compress(b"rootfs_data\x00synthetic-test-only",mtime=0)
        raw[4096:4096+len(fake_cpio)]=fake_cpio
        raw[16384:16384+17*1024*1024]=hashlib.shake_256(
            b"public-mt6990-large-kernel-boundary-test").digest(17*1024*1024)
        compressed=gzip.compress(bytes(raw),compresslevel=9,mtime=0)
        self.assertGreater(len(compressed),16*1024*1024)
        self.assertLess(len(compressed),v.PARTITION_SIZE-v.REQUIRED_FREE_TAIL-v.PAGE)
        self.assertEqual(bytes(raw).count(fake_cpio),1)
        dtb=bytearray(40)
        struct.pack_into(">II",dtb,0,0xd00dfeed,40)
        table=(struct.pack(">8I",0xd7b7ab1e,104,32,32,1,32,v.PAGE,0)
               +struct.pack(">8I",40,64,0,0,0,0,0,0)
               +dtb)
        profile={"cmdline":"root=PARTLABEL=rootfs_data","name":"mt6990",
                 "dtb_addr":32505856,"kernel_addr":0,"ramdisk_addr":0,
                 "second_addr":0,"tags_addr":0,"os_version":0}
        head=bytearray(1660)
        head[:8]=b"ANDROID!"
        struct.pack_into("<10I",head,8,len(compressed),0,0,0,0,0,0,v.PAGE,2,0)
        head[48:54]=b"mt6990"
        head[64:64+len(profile["cmdline"])]=profile["cmdline"].encode()
        digest=hashlib.sha1()
        for data in (compressed,b"",b"",b"",table):
            digest.update(data)
            digest.update(struct.pack("<I",len(data)))
        head[576:596]=digest.digest()
        struct.pack_into("<I",head,1644,1660)
        struct.pack_into("<I",head,1648,len(table))
        struct.pack_into("<Q",head,1652,profile["dtb_addr"])
        def pad(blob):
            return blob+bytes((-len(blob))%v.PAGE)
        partial=pad(head)+pad(compressed)+pad(table)
        self.assertLess(len(partial),v.PARTITION_SIZE-v.REQUIRED_FREE_TAIL)
        p25=partial+bytes(v.PARTITION_SIZE-len(partial))
        rec={"unsigned_p25_sha256":hashlib.sha256(p25).hexdigest()}
        checked=v.check(p25,bytes(raw),bytes(dtb),fake_cpio,profile,rec)
        self.assertEqual(checked["result"],
                         "PUBLIC_UNSIGNED_P25_INDEPENDENT_READBACK_PASS")
        self.assertEqual(checked["p25_bytes"],v.PARTITION_SIZE)


if __name__=="__main__":
    unittest.main()
