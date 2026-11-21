#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Device-free source and negative acceptance gates for proto2 P44."""
import importlib.util
import io
import pathlib
import tarfile
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]

def read(path):
    return (ROOT / path).read_text(encoding="utf-8")

def packager():
    spec = importlib.util.spec_from_file_location("proto2_pkg", ROOT / "scripts/package-proto2-p44.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

class Proto2SourceTests(unittest.TestCase):
    def test_wifi_own_calibration_precedes_load(self):
        script = read("scripts/proto2-wifi-start.sh")
        for token in ("part rootfs_a", "part rootfs_b", "PARTNAME=$wanted",
                      "MT7990_EEPROM.bin", "OWN_EEPROM_ID", "RUN_NOT_TMPFS",
                      "DRIVER_ALREADY_LOADED_WITHOUT_PHY", "sha256sum -c SHA256SUMS",
                      'mount --bind "$stage" "$target"'):
            self.assertIn(token, script)
        self.assertLess(script.index("mount --bind"), script.index('insmod "$mods/mt7996e.ko"'))
        self.assertNotIn("rmmod ", script)
        self.assertNotIn("iw reg set", script)

    def test_private_modules_exactly_pinned(self):
        script = read("scripts/prepare-proto2-wifi-modules.sh")
        module = packager()
        self.assertEqual(len(module.MODULE_SHAS), 3)
        for sha in module.MODULE_SHAS.values():
            self.assertIn(sha, script)
        self.assertIn("--json isPrivate", script)
        self.assertNotIn("MT7990_EEPROM.bin", script)
        self.assertIn("net/wireless/cfg80211.ko", script)
        self.assertIn("net/mac80211/mac80211.ko", script)
        self.assertIn("depmod -b", script)
        package_source = read("scripts/package-proto2-p44.py")
        self.assertIn("base_required", package_source)
        self.assertIn("missing ABI-matched cfg80211/mac80211", package_source)

    def test_firstboot_owner_neutral(self):
        rootfs = read("scripts/build-proto2-p44-rootfs.sh")
        first = read("scripts/p44-firstboot.sh")
        for token in ("passwd -d root", "PermitEmptyPasswords no", "192.168.1.1:22",
                      "-F -E -B -j -k", "terminal6-proto2-wifi.service",
                      "blacklist mt7996e", "ssh.socket",
                      "ConditionPathExists=/var/lib/terminal6/firstboot-complete"):
            self.assertIn(token, rootfs)
        for token in ("verify-start", "firstboot-auth-verified", "firstboot-complete",
                      "systemctl stop terminal6-firstboot.service",
                      "systemctl start ssh.service"):
            self.assertIn(token, first)
        self.assertNotIn('install -m 0600 "$auth"', rootfs)
        self.assertNotIn("terminal6-public-management", rootfs)

    def test_wrong_p25_rejected_without_zip(self):
        module = packager()
        with tempfile.TemporaryDirectory() as temp:
            root = pathlib.Path(temp)
            p25 = root / "P25.img"
            with p25.open("wb") as f:
                f.truncate(33554432)
            rootfs = root / "rootfs.tar.gz"
            rootfs.write_bytes(b"fixture")
            mods = root / "modules.tar"
            with tarfile.open(mods, "w"):
                pass
            release = root / "kernel.release"
            release.write_text("6.18.63-debian-t6-proto2\n")
            with self.assertRaisesRegex(ValueError, "SIGNED P25 hash"):
                module.package(rootfs, mods, p25, release, root / "P44.zip", "a" * 40)
            self.assertFalse((root / "P44.zip").exists())

    def test_unapproved_module_tar_rejected(self):
        module = packager()
        with tempfile.TemporaryDirectory() as temp:
            path = pathlib.Path(temp) / "modules.tar"
            with tarfile.open(path, "w") as file:
                blob = b"untrusted"
                entry = tarfile.TarInfo("lib/modules/6.18.63-debian-t6-proto2/updates/terminal6-mt76/evil.ko")
                entry.size = len(blob)
                file.addfile(entry, io.BytesIO(blob))
            with self.assertRaisesRegex(ValueError, "unapproved module"):
                module.verify_modules_tar(path)

if __name__ == "__main__":
    unittest.main()
