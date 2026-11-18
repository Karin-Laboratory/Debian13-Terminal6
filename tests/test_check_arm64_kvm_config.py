import importlib.util
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "scripts/check_arm64_kvm_config.py"
SPEC = importlib.util.spec_from_file_location("check_arm64_kvm_config", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


class KvmConfigTests(unittest.TestCase):
    def test_enabled_arm64_kvm_passes(self):
        values = {
            "CONFIG_ARM64": "y",
            "CONFIG_VIRTUALIZATION": "y",
            "CONFIG_KVM": "y",
        }
        self.assertEqual(MODULE.validate(values), [])

    def test_current_virtualization_disabled_fails(self):
        values = {"CONFIG_ARM64": "y", "CONFIG_VIRTUALIZATION": "n"}
        self.assertIn("CONFIG_VIRTUALIZATION must be y", MODULE.validate(values))
        self.assertIn("CONFIG_KVM must be built-in (y)", MODULE.validate(values))

    def test_modular_kvm_is_rejected(self):
        values = {
            "CONFIG_ARM64": "y",
            "CONFIG_VIRTUALIZATION": "y",
            "CONFIG_KVM": "m",
        }
        self.assertIn("CONFIG_KVM must be built-in (y)", MODULE.validate(values))

    def test_non_arm64_is_rejected(self):
        values = {
            "CONFIG_ARM64": "n",
            "CONFIG_VIRTUALIZATION": "y",
            "CONFIG_KVM": "y",
        }
        self.assertIn("CONFIG_ARM64 must be y", MODULE.validate(values))

    def test_reads_disabled_symbols(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = Path(tmp) / ".config"
            config.write_text("CONFIG_ARM64=y\n# CONFIG_VIRTUALIZATION is not set\n", encoding="utf-8")
            self.assertEqual(MODULE.read_config(config)["CONFIG_VIRTUALIZATION"], "n")


if __name__ == "__main__":
    unittest.main()
