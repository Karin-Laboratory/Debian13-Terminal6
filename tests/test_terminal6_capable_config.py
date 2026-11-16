# SPDX-License-Identifier: MIT
"""Offline fail-closed tests for capable profile; no device or RF actions."""
import importlib.util
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "capable", ROOT / "scripts/verify-terminal6-capable-config.py")
assert spec is not None and spec.loader is not None
capable = importlib.util.module_from_spec(spec)
spec.loader.exec_module(capable)


class CapableConfigTests(unittest.TestCase):
    def config(self):
        values = dict.fromkeys(
            capable.lean.REQUIRED + capable.lean.BOARD_REQUIRED +
            capable.lean.LEAN_REQUIRED + tuple("CONFIG_" + k for k in capable.BUILTINS),
            "y"
        )
        values.update(dict.fromkeys(
            capable.lean.LEAN_MODULES +
            tuple("CONFIG_" + k for k in capable.MODULES), "m"))
        values["CONFIG_ARM64_VA_BITS"] = "39"
        values["CONFIG_LOCALVERSION"] = capable.EXPECTED_LOCALVERSION
        return "\n".join(f"{k}={v}" for k, v in sorted(values.items())) + "\n"

    def test_complete_profile(self):
        self.assertEqual(capable.problems(self.config()), [])

    def test_missing_kvm_is_rejected(self):
        c = self.config().replace("CONFIG_KVM=y", "# CONFIG_KVM is not set")
        self.assertIn("CONFIG_KVM=y", capable.problems(c))

    def test_mt7996_must_be_real_module(self):
        c = self.config().replace("CONFIG_MT7996E=m", "CONFIG_MT7996E=n")
        self.assertIn("CONFIG_MT7996E=m", capable.problems(c))

    def test_usb_host_not_omitted(self):
        c = self.config().replace("CONFIG_USB_XHCI_MTK=m", "CONFIG_USB_XHCI_MTK=n")
        self.assertIn("CONFIG_USB_XHCI_MTK=m", capable.problems(c))

    def test_lean_ethernet_and_p44_still_required(self):
        c = self.config().replace("CONFIG_MMC_MTK=y", "CONFIG_MMC_MTK=m")
        self.assertIn("CONFIG_MMC_MTK", capable.problems(c))

    def test_private_proto2_module_release_must_not_be_faked(self):
        c = self.config().replace(capable.EXPECTED_LOCALVERSION,
                                  '"-debian-t6-proto2"')
        self.assertIn("CONFIG_LOCALVERSION=-t6-public-capable", capable.problems(c))

    def test_image_limit_is_35_mib_and_not_p25_partition(self):
        self.assertEqual(capable.MAX_IMAGE_BYTES, 36_700_160)
        self.assertEqual(capable.P25_BYTES, 33_554_432)
        with tempfile.TemporaryDirectory() as d:
            cfg = Path(d) / "config"
            img = Path(d) / "Image"
            cfg.write_text(self.config())
            with img.open("wb") as f:
                f.write(bytes(56) + b"ARM" + bytes([0x64]))
                f.truncate(capable.MAX_IMAGE_BYTES + 1)
            with self.assertRaises(SystemExit):
                capable.check(cfg, img)


if __name__ == "__main__":
    unittest.main()
