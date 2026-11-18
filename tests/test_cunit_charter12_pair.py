#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""No device I/O. Verify charter 1.2 firstboot/P44 pair source contracts."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
import zipfile
import io
import tarfile

ROOT = Path(__file__).resolve().parents[1]


class Charter12Test(unittest.TestCase):
    def test_charter_and_agents_are_v12(self):
        charter = (ROOT / "docs/architecture/P25-FOUNDATION-POLICY.ja.md").read_text()
        agents = (ROOT / "AGENTS.md").read_text()
        self.assertIn("版：1.2", charter)
        self.assertIn("P44-install.zip", charter)
        self.assertIn("初回無認証SSH", charter)
        self.assertIn("初回セットアップだけ", agents)

    def test_firstboot_is_separate_from_fail_closed_rescue(self):
        initial = (ROOT / "scripts/firstboot-initramfs.sh").read_text()
        rescue = (ROOT / "scripts/initramfs-rescue.sh").read_text()
        init = (ROOT / "initramfs/init").read_text()
        install = (ROOT / "scripts/install-p44-initramfs.sh").read_text()
        self.assertIn("empty_p44", initial)
        self.assertIn("firstboot-complete", initial)
        self.assertIn("auth-verified", initial)
        self.assertIn("dropbear -B -j -k", initial)
        self.assertIn("-p 192.168.1.1:22", initial)
        self.assertIn("/sbin/terminal6-firstboot probe", init)
        self.assertIn("mount -t ext4", init)
        self.assertIn("firstboot serve", init)
        self.assertIn("-p \"$rescue_ip:2222\"", rescue)
        self.assertIn("-s -g -j -k", rescue)
        self.assertIn("terminal6-firstboot probe", install)
        self.assertIn("sha256sum -c SHA256SUMS", install)

    def test_p44_zip_contains_no_raw_p25_and_has_matching_manifest(self):
        spec = importlib.util.spec_from_file_location(
            "package_p44", ROOT / "scripts/package-p44-install.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            rootfs = d / "rootfs.tar.gz"
            with tarfile.open(rootfs, "w:gz") as t:
                contents = b"dummy debian tree fixture"
                ti = tarfile.TarInfo("./file")
                ti.size = len(contents)
                t.addfile(ti, io.BytesIO(contents))
            modules = d / "modules.tar"
            with tarfile.open(modules, "w") as t:
                pass
            p25 = d / "p25-unsigned.img"
            with p25.open("wb") as f:
                f.truncate(33554432)
            release = d / "kernel.release"
            release.write_text("6.18.63-t6-public-capable\n")
            output = d / "P44-install.zip"
            module.package(rootfs, modules, p25, release, output, "a" * 40)
            with zipfile.ZipFile(output) as z:
                self.assertNotIn("p25-unsigned.img", z.namelist())
                self.assertEqual(set(z.namelist()), {
                    "rootfs.tar.gz", "modules.tar", "manifest.json",
                    "kernel.release", "SHA256SUMS", "INSTALL-STATUS.txt",
                })
                manifest = json.loads(z.read("manifest.json"))
                self.assertEqual(manifest["charter_version"], "1.2")
                self.assertEqual(manifest["p25_unsigned"]["bytes"], 33554432)
                self.assertEqual(manifest["kernel_release"], release.read_text().strip())
                self.assertIn("NOT SIGNED", z.read("INSTALL-STATUS.txt").decode())


if __name__ == "__main__":
    unittest.main()
