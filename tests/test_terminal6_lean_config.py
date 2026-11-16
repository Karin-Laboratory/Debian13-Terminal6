# SPDX-License-Identifier: MIT
"""Static contract tests for the public Terminal6 lean kernel profile.

These do not claim Kconfig resolution or physical boot. CI builds Linux for that.
"""
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("verify_kconfig", ROOT / "scripts/verify-kconfig.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class LeanKernelContractTests(unittest.TestCase):
    def config(self):
        required = set(module.REQUIRED) | set(module.BOARD_REQUIRED) | set(module.LEAN_REQUIRED)
        return ("\n".join(f"{key}=y" for key in sorted(required))
                + "\nCONFIG_ARM64_VA_BITS=39\n"
                + "\n".join(f"{key}=m" for key in module.LEAN_MODULES)
                + "\n")

    def test_valid_expected_builtin_and_modular_contract(self):
        cfg = self.config()
        self.assertEqual(module.missing(cfg, board=True), [])
        self.assertEqual(module.lean_problems(cfg), [])

    def test_mmc_must_be_builtin(self):
        cfg = self.config().replace("CONFIG_MMC_MTK=y", "CONFIG_MMC_MTK=m")
        self.assertIn("CONFIG_MMC_MTK", module.missing(cfg, board=True))

    def test_ethernet_dsa_must_be_builtin(self):
        cfg = self.config().replace("CONFIG_NET_MEDIATEK_SOC=y", "CONFIG_NET_MEDIATEK_SOC=m")
        self.assertIn("CONFIG_NET_MEDIATEK_SOC", module.missing(cfg, board=True))

    def test_modular_overlay_must_not_be_missing(self):
        cfg = self.config().replace("CONFIG_OVERLAY_FS=m", "# CONFIG_OVERLAY_FS is not set")
        self.assertIn("CONFIG_OVERLAY_FS=m", module.lean_problems(cfg))

    def test_va39_required(self):
        cfg = self.config().replace("CONFIG_ARM64_VA_BITS=39", "CONFIG_ARM64_VA_BITS=48")
        self.assertIn("CONFIG_ARM64_VA_BITS=39", module.lean_problems(cfg))


if __name__ == "__main__":
    unittest.main()
