import importlib.util
from pathlib import Path
import struct
import unittest

ROOT = Path(__file__).resolve().parents[1]

def load(name, file):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / file)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

config = load("config_checker", "verify-kconfig.py")
p25 = load("p25_checker", "check-unsigned-p25.py")

class CheckTests(unittest.TestCase):
    def test_missing_config(self):
        self.assertIn("CONFIG_EXT4_FS", config.missing("CONFIG_MMC=y\n"))
    def test_complete_config(self):
        self.assertEqual([], config.missing("".join(f"{k}=y\n" for k in config.REQUIRED)))
    def test_reject_truncated_p25(self):
        with self.assertRaisesRegex(ValueError, "expected"):
            p25.inspect(b"ANDROID!")
    def test_header_fixture(self):
        data = bytearray(p25.P25_BYTES)
        data[:8] = b"ANDROID!"
        struct.pack_into("<I", data, 8, 1024)
        struct.pack_into("<I", data, 36, 4096)
        struct.pack_into("<I", data, 40, 2)
        self.assertEqual(p25.inspect(data)["header_version"], 2)

class BootRegressionTests(unittest.TestCase):
    def test_silent_or_non_executable_kernel_rejected(self):
        complete = "".join(f"{k}=y\n" for k in config.REQUIRED)
        for key in ("CONFIG_PRINTK", "CONFIG_BINFMT_ELF", "CONFIG_ARM_GIC_V3", "CONFIG_ARM_ARCH_TIMER"):
            self.assertIn(key, config.missing(complete.replace(f"{key}=y\n", "")))

    def test_generic_network_does_not_establish_board_support(self):
        generic = "".join(f"{k}=y\n" for k in config.REQUIRED)
        self.assertIn("CONFIG_NET_MEDIATEK_SOC", config.missing(generic, board=True))
