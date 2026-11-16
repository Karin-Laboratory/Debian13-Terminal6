# SPDX-License-Identifier: MIT
"""Full35 presence gates, independent from expensive ARM64 native build."""
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("verify_kconfig", ROOT / "scripts/verify-kconfig.py")
v = importlib.util.module_from_spec(spec)
spec.loader.exec_module(v)

class Full35Tests(unittest.TestCase):
    def sample(self):
        return ("\n".join(x + "=y" for x in (*v.REQUIRED, *v.BOARD_REQUIRED,
                                             *v.LEAN_REQUIRED, *v.FULL35_BUILTINS))
                + "\nCONFIG_ARM64_VA_BITS=39\n"
                + "\n".join(x + "=m" for x in (*v.LEAN_MODULES, *v.FULL35_MODULES))
                + "\n")

    def test_valid_profile(self):
        self.assertEqual(v.full35_problems(self.sample()), [])
    def test_kvm_missing_fails(self):
        self.assertIn("CONFIG_KVM", v.full35_problems(self.sample().replace(
            "CONFIG_KVM=y", "# CONFIG_KVM is not set")))
    def test_wifi_missing_fails(self):
        self.assertIn("CONFIG_MT7996E=m", v.full35_problems(self.sample().replace(
            "CONFIG_MT7996E=m", "# CONFIG_MT7996E is not set")))
    def test_usb_missing_fails(self):
        self.assertIn("CONFIG_USB_XHCI_HCD=m", v.full35_problems(self.sample().replace(
            "CONFIG_USB_XHCI_HCD=m", "# CONFIG_USB_XHCI_HCD is not set")))
    def test_board_netdev_builtin(self):
        self.assertIn("CONFIG_NET_MEDIATEK_SOC", v.missing(
            self.sample().replace("CONFIG_NET_MEDIATEK_SOC=y", "CONFIG_NET_MEDIATEK_SOC=m"), board=True))

if __name__=="__main__":
    unittest.main()
