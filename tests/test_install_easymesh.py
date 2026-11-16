import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).parents[1]
INSTALLER = ROOT / "packaging/easymesh/install-easymesh.sh"
BINARIES = ("ieee1905_transport", "beerocks_controller", "beerocks_agent", "beerocks_vendor_message")


def machine(path: Path) -> str:
    result = subprocess.run(["readelf", "-h", str(path)], check=True, capture_output=True, text=True)
    for line in result.stdout.splitlines():
        if "Machine:" in line:
            return line.split("Machine:", 1)[1].strip()
    raise AssertionError("ELF Machine field absent")


class InstallerTests(unittest.TestCase):
    def setUp(self):
        if not shutil.which("readelf"):
            self.skipTest("binutils readelf unavailable")
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.prefix = self.root / "prefix"
        (self.prefix / "bin").mkdir(parents=True)
        for name in BINARIES:
            shutil.copy2("/bin/true", self.prefix / "bin" / name)
            (self.prefix / "bin" / name).chmod(0o755)
        self.acl = self.root / "prplmesh.json"
        self.acl.write_text("{}\n")

    def tearDown(self):
        self.temp.cleanup()

    def test_wrong_architecture_fails_before_install(self):
        destination = self.root / "wrong-arch-stage"
        env = dict(os.environ, DESTDIR=str(destination))
        result = subprocess.run(
            [str(INSTALLER), str(self.prefix), str(self.acl), "AArch64"],
            env=env, capture_output=True, text=True, check=False,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("wrong ELF machine", result.stderr)
        self.assertFalse(destination.exists())

    def test_matching_architecture_stages_files_without_enabling_service(self):
        destination = self.root / "right-arch-stage"
        env = dict(os.environ, DESTDIR=str(destination))
        result = subprocess.run(
            [str(INSTALLER), str(self.prefix), str(self.acl), machine(self.prefix / "bin/ieee1905_transport")],
            env=env, capture_output=True, text=True, check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((destination / "opt/terminal6-easymesh/bin/beerocks_agent").is_file())
        self.assertTrue((destination / "etc/acl/admin/prplmesh.json").is_file())
        self.assertFalse((destination / "etc/terminal6-easymesh/enabled").exists())


if __name__ == "__main__":
    unittest.main()
