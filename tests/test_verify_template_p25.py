import gzip
import importlib.util
from pathlib import Path
import struct
import unittest

root=Path(__file__).resolve().parents[1]/"scripts"
def load(n,p):
    s=importlib.util.spec_from_file_location(n,root/p)
    m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
producer=load("producer","assemble-template-p25.py")
verifier=load("verifier","verify-template-p25.py")

class VerifyTest(unittest.TestCase):
    def test_verify_and_mutation(self):
        template=bytearray(producer.SIZE)
        template[:8]=b"ANDROID!"
        struct.pack_into("<I",template,8,4096)
        struct.pack_into("<II",template,36,2048,2)
        struct.pack_into("<I",template,1644,1660)
        struct.pack_into("<I",template,1648,104)
        old=6144
        template[old+64:old+68]=producer.FDT
        struct.pack_into(">I",template,old+68,40)
        dtb=bytearray(40);dtb[:4]=producer.FDT;struct.pack_into(">I",dtb,4,40)
        init=gzip.compress(b"/dev/mmcblk0p44",mtime=0)
        kernel=gzip.compress(b"MZ\x00\x00"+bytes(100)+init+bytes(1024),mtime=0)
        image,_=producer.produce(bytes(template),kernel,bytes(dtb),init,"root=/dev/mmcblk0p44")
        receipt=verifier.verify(image,kernel,bytes(dtb),init,bytes(template))
        self.assertEqual(receipt["status"],"UNSIGNED_P25_INDEPENDENT_STRUCTURAL_PASS")
        broken=bytearray(image);broken[576]^=1
        with self.assertRaises(ValueError):
            verifier.verify(bytes(broken),kernel,bytes(dtb),init,bytes(template))
