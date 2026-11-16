import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest

SCRIPT = Path(__file__).parents[1] / "packaging/easymesh/verify-arm64-linker.py"
spec = importlib.util.spec_from_file_location("easymesh_arm64_linker", SCRIPT)
module = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(module)


class LoaderTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.sysroot = root / "arm64"
        self.stage_lib = root / "stage/lib"
        self.binary = root / "stage/bin/beerocks_agent"
        self.binary.parent.mkdir(parents=True)
        self.binary.write_bytes(b"synthetic fixture, not an ELF")
        self.stage_lib.mkdir(parents=True)
        self.loader = self.sysroot / "lib/ld-linux-aarch64.so.1"
        self.loader.parent.mkdir(parents=True)
        self.loader.write_bytes(b"synthetic loader fixture")
        self.commands = []

    def tearDown(self):
        self.tmp.cleanup()

    def fake_run(self, argv, **kwargs):
        self.commands.append(argv)
        if argv[:2] == ["readelf", "-h"]:
            return subprocess.CompletedProcess(argv, 0, "  Machine:                           AArch64\n", "")
        if argv[:2] == ["readelf", "-l"]:
            return subprocess.CompletedProcess(argv, 0,
                                               "  [Requesting program interpreter: /lib/ld-linux-aarch64.so.1]\n", "")
        return subprocess.CompletedProcess(argv, 0,
                                           "\tlibc.so.6 => /lib/aarch64-linux-gnu/libc.so.6 (0x0000)\n", "")

    def test_loader_is_invoked_with_list_only_and_target_prefix(self):
        output = module.inspect(self.binary, self.sysroot, self.stage_lib, "qemu-aarch64", run=self.fake_run)
        self.assertEqual(output["result"], "loader-libraries-resolved")
        command = self.commands[-1]
        self.assertEqual(command[0:3], ["qemu-aarch64", "-L", str(self.sysroot)])
        self.assertEqual(command[3], str(self.loader))
        self.assertEqual(command[-2:], ["--list", str(self.binary)])
        self.assertIn(str(self.stage_lib), command[command.index("--library-path") + 1])

    def test_non_arm64_elf_is_rejected(self):
        def wrong_arch(argv, **kwargs):
            if argv[:2] == ["readelf", "-h"]:
                return subprocess.CompletedProcess(argv, 0, "Machine: Advanced Micro Devices X86-64\n", "")
            return self.fake_run(argv, **kwargs)
        with self.assertRaisesRegex(module.LoaderCheckError, "AArch64"):
            module.inspect(self.binary, self.sysroot, self.stage_lib, "qemu-aarch64", run=wrong_arch)

    def test_missing_target_loader_is_rejected(self):
        self.loader.unlink()
        with self.assertRaisesRegex(module.LoaderCheckError, "interpreter missing"):
            module.inspect(self.binary, self.sysroot, self.stage_lib, "qemu-aarch64", run=self.fake_run)

    def test_missing_library_is_rejected(self):
        def missing_library(argv, **kwargs):
            if argv[0] == "qemu-aarch64":
                return subprocess.CompletedProcess(argv, 0, "libmissing.so => not found\n", "")
            return self.fake_run(argv, **kwargs)
        with self.assertRaisesRegex(module.LoaderCheckError, "unresolved target libraries"):
            module.inspect(self.binary, self.sysroot, self.stage_lib, "qemu-aarch64", run=missing_library)

    def test_loader_failure_is_not_reported_as_success(self):
        def failed_loader(argv, **kwargs):
            if argv[0] == "qemu-aarch64":
                return subprocess.CompletedProcess(argv, 1, "", "invalid binary")
            return self.fake_run(argv, **kwargs)
        with self.assertRaisesRegex(module.LoaderCheckError, "loader failure"):
            module.inspect(self.binary, self.sysroot, self.stage_lib, "qemu-aarch64", run=failed_loader)

    def test_empty_output_is_not_reported_as_success(self):
        def empty_loader(argv, **kwargs):
            if argv[0] == "qemu-aarch64":
                return subprocess.CompletedProcess(argv, 0, "", "")
            return self.fake_run(argv, **kwargs)
        with self.assertRaisesRegex(module.LoaderCheckError, "no resolved"):
            module.inspect(self.binary, self.sysroot, self.stage_lib, "qemu-aarch64", run=empty_loader)


if __name__ == "__main__":
    unittest.main()
