import importlib.util
from pathlib import Path
import unittest

p=Path(__file__).resolve().parents[1]/"scripts/prepare-experimental-dts.py"
s=importlib.util.spec_from_file_location("dts",p)
m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
class TestDTS(unittest.TestCase):
    def test_only_mmc0(self):
        data='model = "SoftBank Air Terminal 6 (research)";\n&mmc0 {\n status = "disabled";\n};\n&eth { status = "disabled"; };'
        result=m.enable_emmc(data)
        self.assertIn('&mmc0 {\n status = "okay";',result)
        self.assertIn('max-frequency = <100000000>;',result)
        self.assertNotIn('supports-cqe',result)
        self.assertIn('&eth { status = "disabled"; };',result)
    def test_refuse_both_existing_frequency_and_cqe(self):
        base='&mmc0 {\\n max-frequency = <200000000>;\\n status = "disabled";\\n};'
        with self.assertRaises(ValueError):m.enable_emmc(base)
        base='&mmc0 {\\n supports-cqe;\\n status = "disabled";\\n};'
        with self.assertRaises(ValueError):m.enable_emmc(base)
    def test_missing(self):
        with self.assertRaises(ValueError):m.enable_emmc('&mmc1 { status = "disabled"; };')
