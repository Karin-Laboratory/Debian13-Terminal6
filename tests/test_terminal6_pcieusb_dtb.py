# SPDX-License-Identifier: MIT
"""Offline contract checks for PCIe/USB enabled source-only C-unit DTB."""
from pathlib import Path
import importlib.util
import unittest

ROOT = Path(__file__).resolve().parents[1]
def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod
dtb = load("pcieusb_dtb", ROOT / "scripts/prepare-pcie-usb-experimental-dts.py")
verify = load("pcieusb_verify", ROOT / "scripts/verify-terminal6-pcieusb-config.py")

class ExperimentalDTBTests(unittest.TestCase):
    def test_overlay_enables_complete_tree(self):
        out = dtb.make_overlay(dtb.SOURCE_BASE_INCLUDE + "\n&eth { status = \"okay\"; };\n")
        for node in ("pcie0","pcie1","pcie2","pciephy0","pciephy1","pciephy2",
                     "usb","xsphy","xhci"):
            self.assertIn("&" + node + " {", out)
        self.assertIn('dr_mode = "host"', out)
        self.assertIn('"mediatek,mt6980-pcie-phy"', out)

    def test_requires_exact_pinned_baseline(self):
        with self.assertRaises(ValueError):
            dtb.make_overlay('&eth { status = "okay"; };')

    def test_preexisting_phy_override_fails_closed(self):
        with self.assertRaises(ValueError):
            dtb.make_overlay(dtb.SOURCE_BASE_INCLUDE + '\n&eth { status = "okay"; };\n&pciephy0 { status = "okay"; };\n')

class FeatureConfigTests(unittest.TestCase):
    def config(self):
        c=verify.capable
        data=dict.fromkeys(c.lean.REQUIRED+c.lean.BOARD_REQUIRED+c.lean.LEAN_REQUIRED+
                           tuple("CONFIG_"+x for x in c.BUILTINS), "y")
        data.update(dict.fromkeys(c.lean.LEAN_MODULES+
                                  tuple("CONFIG_"+x for x in c.MODULES), "m"))
        data.update(dict.fromkeys(("CONFIG_"+x for x in verify.PCIEUSB_MODULES), "m"))
        data.update(dict.fromkeys(("CONFIG_"+x for x in verify.PCIEUSB_BUILTINS), "y"))
        data["CONFIG_ARM64_VA_BITS"]="39"
        data["CONFIG_LOCALVERSION"]=verify.EXPECTED_LOCALVERSION
        return "\n".join(k+"="+v for k,v in sorted(data.items()))+"\n"

    def test_pcie_usb_config(self):
        self.assertEqual(verify.problems(self.config()), [])

    def test_xsphy_missing_fails(self):
        self.assertIn("CONFIG_PHY_MTK_XSPHY=m", verify.problems(self.config().replace(
            "CONFIG_PHY_MTK_XSPHY=m", "# CONFIG_PHY_MTK_XSPHY is not set")))

    def test_mtu3_host_missing_fails(self):
        self.assertIn("CONFIG_USB_MTU3_HOST=y", verify.problems(self.config().replace(
            "CONFIG_USB_MTU3_HOST=y", "# CONFIG_USB_MTU3_HOST is not set")))

    def test_distinct_kernel_abi(self):
        self.assertIn('CONFIG_LOCALVERSION="-t6-public-pcieusb"', verify.problems(
            self.config().replace('CONFIG_LOCALVERSION="-t6-public-pcieusb"',
                                  'CONFIG_LOCALVERSION="-t6-public-capable"')))

if __name__=="__main__":
    unittest.main()
