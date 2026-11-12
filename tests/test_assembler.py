import gzip
import importlib.util
from pathlib import Path
import struct
import unittest

path=Path(__file__).resolve().parents[1]/"scripts/assemble-unsigned-p25.py"
spec=importlib.util.spec_from_file_location("packer",path)
packer=importlib.util.module_from_spec(spec)
spec.loader.exec_module(packer)

class PackerTest(unittest.TestCase):
    def valid(self):
        image = b"MZ\x00\x91"+bytes(52)+b"ARM\x64"+bytes(4040)
        image_gz=gzip.compress(image,mtime=0)
        dtb=bytearray(40)
        dtb[:4]=packer.FDT
        struct.pack_into(">I",dtb,4,len(dtb))
        return image_gz,bytes(dtb),bytes(64)
    def test_boot_image(self):
        b,receipt=packer.produce(*self.valid(),0x40080000,0x40000100,"console=ttyS0")
        self.assertEqual(len(b),33554432)
        self.assertEqual(b[:8],b"ANDROID!")
        self.assertEqual(struct.unpack_from("<I",b,40)[0],2)
        self.assertEqual(receipt["status"],"UNSIGNED_STRUCTURAL_CANDIDATE_NOT_LK_VERIFIED")
    def test_bad_dtb(self):
        a,b,c=self.valid()
        with self.assertRaises(ValueError):
            packer.produce(a,b"bad",c,0,0,"")
    def test_bad_vendor(self):
        a,b,c=self.valid()
        with self.assertRaises(ValueError):
            packer.produce(a,b,b"bad",0,0,"")
