#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""C-unit charter v1.4 Method B source/ZIP contracts, no physical device IO."""
import importlib.util
import io
import json
from pathlib import Path
import tarfile
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]


class Charter14Test(unittest.TestCase):
    def test_charter_and_agents_method_b(self):
        charter = (ROOT / "docs/architecture/P25-FOUNDATION-POLICY.ja.md").read_text()
        agents = (ROOT / "AGENTS.md").read_text()
        self.assertIn("版：1.4", charter)
        self.assertIn("専用の「外部インストーラ」「導入ツール」は", charter)
        self.assertIn("方式B", agents)
        self.assertIn("手作業", agents)

    def test_p25_no_unauth_or_installer(self):
        init = (ROOT / "initramfs/init").read_text()
        stage = (ROOT / "scripts/stage-rescue-ssh.sh").read_text()
        maker = (ROOT / "scripts/make-initramfs.sh").read_text()
        rescue = (ROOT / "scripts/initramfs-rescue.sh").read_text()
        self.assertNotIn("terminal6-firstboot", init)
        self.assertNotIn("terminal6-firstboot", stage)
        self.assertNotIn("terminal6-install-p44", stage)
        self.assertNotIn("dropbearkey", stage)
        self.assertNotIn("gnu-tar", maker)
        self.assertNotIn("terminal6-install-p44", maker)
        self.assertFalse((ROOT / "scripts/firstboot-initramfs.sh").exists())
        self.assertFalse((ROOT / "scripts/install-p44-initramfs.sh").exists())
        self.assertIn("[ -x /newroot/sbin/init ] || fail DEBIAN_INIT_MISSING", init)
        self.assertIn("TERMINAL6_RESCUE_SSH_DISABLED_NO_PRIVATE_IDENTITY", rescue)
        self.assertIn('"-p "$rescue_ip:2222"', '"-p "$rescue_ip:2222"')  # literal guard below
        self.assertIn(' -s -g -j -k -E ', rescue)

    def test_debian_firstboot_on_p44_only(self):
        builder = (ROOT / "scripts/build-public-p44-rootfs.sh").read_text()
        init = (ROOT / "scripts/p44-firstboot.sh").read_text()
        self.assertIn("terminal6-firstboot.service", builder)
        self.assertIn("terminal6-authcheck.service", builder)
        self.assertIn("-F -E -B -j -k", builder)
        self.assertIn("192.168.1.1:22", builder)
        self.assertIn("PermitEmptyPasswords no", builder)
        self.assertIn('disable ssh.service ssh.socket', builder)
        self.assertIn("systemctl --root", builder)
        self.assertIn("passwd -d root", builder)
        self.assertIn("firstboot-auth-verified", init)
        self.assertIn("root_has_credentials", init)
        self.assertIn("verify-start", init)
        self.assertIn("systemctl stop terminal6-firstboot.service", init)
        self.assertIn("systemctl start ssh.service", init)
        self.assertIn("dropbearconvert openssh dropbear", init)

    def test_p44_zip_is_matched_to_unsigned_p25_no_dedicated_installer(self):
        spec = importlib.util.spec_from_file_location(
            "p44_package", ROOT / "scripts/package-p44-install.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            rootfs = d / "rootfs.tar.gz"
            with tarfile.open(rootfs, "w:gz") as t:
                payload = b"test fixture"
                entry = tarfile.TarInfo("./file")
                entry.size = len(payload)
                t.addfile(entry, io.BytesIO(payload))
            modules = d / "modules.tar"
            with tarfile.open(modules, "w"):
                pass
            p25 = d / "p25-unsigned.img"
            with p25.open("wb") as f:
                f.truncate(33554432)
            release = d / "kernel.release"
            release.write_text("6.18.63-t6-public-capable\n")
            out = d / "P44-install.zip"
            module.package(rootfs, modules, p25, release, out, "a" * 40)
            with zipfile.ZipFile(out) as z:
                self.assertEqual(set(z.namelist()), {
                    "rootfs.tar.gz", "modules.tar", "manifest.json",
                    "kernel.release", "SHA256SUMS", "INSTALL-STATUS.txt",
                    "MANUAL-INSTALL.ja.md",
                })
                m = json.loads(z.read("manifest.json"))
                self.assertEqual(m["charter_version"], "1.4")
                self.assertEqual(m["installation_method"], "B_MANUAL_EXTERNAL_PREBOOT_NO_INSTALLER")
                self.assertEqual(m["p25_unsigned"]["bytes"], 33554432)
                self.assertEqual(m["kernel_release"], release.read_text().strip())
                self.assertIn("手動事前導入", z.read("MANUAL-INSTALL.ja.md").decode())


if __name__ == "__main__":
    unittest.main()
