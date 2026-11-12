import importlib.util
from pathlib import Path
import gzip
import struct
import unittest

p=Path(__file__).resolve().parents[1]/"scripts/assemble-template-p25.py"
s=importlib.util.spec_from_file_location("p25template",p)
m=importlib.util.module_from_spec(s);s.loader.exec_module(m)

class TemplateTest(unittest.TestCase):
    def make(self):
        template=bytearray(m.SIZE)
        template[:8]=b"ANDROID!"
        struct.pack_into("<I",template,8,4096)
        struct.pack_into("<II",template,36,2048,2)
        struct.pack_into("<I",template,1644,1660)
        struct.pack_into("<I",template,1648,104)
        pos=2048+4096
        template[pos:pos+64]=bytes(64)
        template[pos+64:pos+68]=m.FDT
        struct.pack_into(">I",template,pos+68,40)
        dtb=bytearray(40)
        dtb[:4]=m.FDT
        struct.pack_into(">I",dtb,4,40)
        cpio=gzip.compress(b"/dev/mmcblk0p44",mtime=0)
        image=gzip.compress(b"MZ\x00\x00"+bytes(100)+cpio+bytes(1024),mtime=0)
        return bytes(template),image,bytes(dtb),cpio
    def test_built_template(self):
        out,receipt=m.produce(*self.make(),"root=/dev/mmcblk0p44")
        self.assertEqual(len(out),m.SIZE)
        self.assertEqual(receipt["status"],"UNSIGNED_P25_TEMPLATE_PRESERVED_NOT_BOOT_VALIDATED")
    def test_wrong_sections(self):
        template,im,dtb,cpio=self.make()
        temp=bytearray(template);struct.pack_into("<I",temp,16,1)
        with self.assertRaises(ValueError):
            m.produce(bytes(temp),im,dtb,cpio,"")
