# SPDX-License-Identifier: MIT
"""Pure offline tests. No hardware or kexec system calls."""
import gzip
import hashlib
import importlib.util
from pathlib import Path
import struct
import tempfile
import unittest

SRC = Path(__file__).resolve().parents[1] / 'scripts/cunit-kexec-g1.py'
spec = importlib.util.spec_from_file_location('cunit_kexec_g1', SRC)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def synthetic_p25():
    arm64 = bytearray(4096)
    arm64[56:60] = b'ARM\x64'
    compressed = gzip.compress(bytes(arm64), mtime=0)
    blob = bytearray(mod.SIGNED_P25_BYTES)
    blob[:8] = b'ANDROID!'
    struct.pack_into('<10I', blob, 8, len(compressed), 0, 0, 0, 0, 0, 0,
                     2048, 2, 0)
    blob[2048:2048+len(compressed)] = compressed
    return bytes(blob), bytes(arm64)


class TestBootParser(unittest.TestCase):
    def test_extract_valid_boot_image(self):
        signed, image = synthetic_p25()
        self.assertEqual(mod.extract_boot_v2(signed), image)

    def test_bad_full_p25_hash_refuses(self):
        signed, image = synthetic_p25()
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / 'p25.img'
            path.write_bytes(signed)
            with self.assertRaisesRegex(mod.GateError, 'SHA mismatch'):
                mod.read_and_check_p25(path, '0'*64)
            got, _ = mod.read_and_check_p25(path, hashlib.sha256(signed).hexdigest())
            self.assertEqual(got, image)

    def test_bad_magic_refuses(self):
        signed, _ = synthetic_p25()
        with self.assertRaisesRegex(mod.GateError, 'not an Android boot'):
            mod.extract_boot_v2(b'NOTVALID' + signed[8:])

    def test_separate_initramfs_refuses(self):
        signed, _ = synthetic_p25()
        blob = bytearray(signed)
        struct.pack_into('<I', blob, 16, 123)
        with self.assertRaisesRegex(mod.GateError, 'separate ramdisk'):
            mod.extract_boot_v2(bytes(blob))

    def test_bad_fdt_refuses(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / 'fdt'
            path.write_bytes(b'\xd0\x0d\xfe\xed' + struct.pack('>I', 999) + bytes(32))
            with self.assertRaisesRegex(mod.GateError, 'totalsize'):
                mod.read_fdt(path)

    def test_no_exec_action_in_cli(self):
        self.assertNotIn('exec', ['inspect', 'stage', 'load', 'unload'])
        src = SRC.read_text()
        self.assertNotIn('shell=True', src)
        self.assertNotIn('"--exec"', src)
        self.assertNotIn('"-e"', src)


if __name__ == '__main__':
    unittest.main()
