#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Device-free source and negative acceptance gates for proto2 P44."""
import importlib.util
import io
import pathlib
import hashlib
import struct
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

    def test_wifi_p26_ext4_is_not_a_fatal_prerequisite(self):
        script = read("scripts/proto2-wifi-start.sh")
        self.assertIn("ROOTFS_A_NOT_SQUASHFS_SKIPPED", script)
        self.assertIn("FIRMWARE_SOURCE_THIS_UNIT_STOCK_B", script)
        self.assertIn("FIRMWARE_SOURCE_OWNER_PRIVATE", script)
        self.assertIn("PRIVATE_FIRMWARE_SHA", script)
        self.assertIn("FIRMWARE_SOURCE_NOT_FOUND_NO_P26_FORMAT_ASSUMPTION", script)
        self.assertIn("blkid -p -o value -s TYPE", script)
        self.assertNotIn("ROOTFS_A_RO_MOUNT", script)
        self.assertLess(script.index('mount -t squashfs -o ro "$(part rootfs_b)"'),
                        script.index('if [ "$(blkid'))
        self.assertIn('umount "$stock"', script)

    def test_slot_a_success_misc_patch_is_exact_and_idempotent(self):
        mod = self._slot_module()
        before = bytearray(b"\x5a" * mod.MISC_BYTES)
        before[mod.CTRL_OFFSET:mod.CTRL_OFFSET + 10] = bytes.fromhex("0f040000000e00010000")
        after, changed = mod.patch_misc(bytes(before))
        self.assertTrue(changed)
        self.assertEqual(after[mod.CTRL_OFFSET:mod.CTRL_OFFSET + 10],
                         bytes.fromhex("0f000100000e00010000"))
        self.assertEqual([i for i in range(len(before)) if before[i] != after[i]],
                         [mod.CTRL_OFFSET + 1, mod.CTRL_OFFSET + 2])
        again, changed = mod.patch_misc(after)
        self.assertFalse(changed)
        self.assertEqual(again, after)

    def test_slot_a_success_unknown_layout_fails_closed(self):
        mod = self._slot_module()
        data = bytearray(mod.MISC_BYTES)
        data[mod.CTRL_OFFSET:mod.CTRL_OFFSET + 10] = bytes.fromhex("0f040000000e00010000")
        for offset, value in ((mod.CTRL_OFFSET, 0x00),
                              (mod.CTRL_OFFSET + 5, 0x0f),
                              (mod.CTRL_OFFSET + 7, 0x00),
                              (mod.CTRL_OFFSET + 1, 0x00)):
            mutated = bytearray(data)
            mutated[offset] = value
            with self.assertRaises(RuntimeError):
                mod.patch_misc(bytes(mutated))
        with self.assertRaises(RuntimeError):
            mod.patch_misc(bytes(data[:4096]))

    @staticmethod
    def _slot_module():
        spec = importlib.util.spec_from_file_location(
            "proto2_slot_a_success", ROOT / "scripts/proto2-slot-a-success.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_slot_a_success_service_requires_owner_arming(self):
        rootfs = read("scripts/build-proto2-p44-rootfs.sh")
        validator = read("scripts/proto2-slot-a-success.py")
        self.assertIn("terminal6-slot-a-success.service", rootfs)
        self.assertIn("ConditionPathExists=/etc/terminal6/authorize-slot-a-success", rootfs)
        self.assertIn("ALLOW_CUNIT_PROTO2_SLOT_A_SUCCESS_V1", validator)
        self.assertIn("CURRENT_BOOT_EEPROM_ACK_MISSING", validator)
        self.assertIn("CURRENT_BOOT_OTP_ACK_MISSING", validator)
        self.assertIn("UNEXPECTED_BOOT_A_SHA", validator)
        self.assertIn("SLOT_A_SUCCESS_READY_DRY_RUN_ONLY", validator)
        self.assertNotIn("enable terminal6-slot-a-success.service", rootfs)

    def test_private_modules_exactly_pinned(self):
        script = read("scripts/prepare-proto2-wifi-modules.sh")
        module = packager()
        self.assertEqual(len(module.MODULE_SHAS), 3)
        for sha in module.MODULE_SHAS.values():
            self.assertIn(sha, script)
        self.assertIn("--json isPrivate", script)
        private = read("scripts/fetch-proto2-private-baseline.sh")
        self.assertIn("442014649e3e384535919fad40e19d2993464f20f1059c77fa4741c017a66abb", private)
        self.assertIn("74c1c98b31cdba54f71d16f1983fbeff347bb334c5ae7d7f1353cd57f734936e", private)
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

    @staticmethod
    def _synthetic_arm64_init():
        binary = bytearray(192)
        binary[:6] = b"\x7fELF\x02\x01"
        struct.pack_into("<H", binary, 18, 183)
        struct.pack_into("<Q", binary, 32, 64)
        struct.pack_into("<H", binary, 54, 56)
        struct.pack_into("<H", binary, 56, 1)
        interpreter = b"/lib/ld-linux-aarch64.so.1\x00"
        struct.pack_into("<I", binary, 64, 3)
        struct.pack_into("<Q", binary, 72, 128)
        struct.pack_into("<Q", binary, 96, len(interpreter))
        binary[128:128 + len(interpreter)] = interpreter
        return bytes(binary)

    @staticmethod
    def _write_init_tar(path, include_loader=True, include_init=True):
        directory = ["usr", "usr/sbin", "usr/lib", "usr/lib/systemd"]
        links = {"sbin": "usr/sbin", "lib": "usr/lib"}
        if include_init:
            links["usr/sbin/init"] = "../lib/systemd/systemd"
        with tarfile.open(path, "w:gz") as archive:
            for name in directory:
                entry = tarfile.TarInfo("./" + name)
                entry.type = tarfile.DIRTYPE
                entry.mode = 0o755
                archive.addfile(entry)
            for name, target in links.items():
                entry = tarfile.TarInfo("./" + name)
                entry.type = tarfile.SYMTYPE
                entry.linkname = target
                archive.addfile(entry)
            content = Proto2SourceTests._synthetic_arm64_init()
            entry = tarfile.TarInfo("./usr/lib/systemd/systemd")
            entry.size = len(content)
            entry.mode = 0o755
            archive.addfile(entry, io.BytesIO(content))
            if include_loader:
                entry = tarfile.TarInfo("./usr/lib/ld-linux-aarch64.so.1")
                entry.mode = 0o755
                entry.size = 4
                archive.addfile(entry, io.BytesIO(b"ELF!"))

    def test_p44_init_archive_merged_usr_and_interpreter(self):
        module = packager()
        with tempfile.TemporaryDirectory() as temp:
            rootfs = pathlib.Path(temp) / "rootfs.tar.gz"
            self._write_init_tar(rootfs)
            state = module.verify_bootable_proto2_rootfs(rootfs)
            self.assertEqual(state["init_path"], "usr/lib/systemd/systemd")
            self.assertEqual(state["interpreter_path"], "usr/lib/ld-linux-aarch64.so.1")

    def test_p44_init_archive_rejects_missing_interpreter_and_init(self):
        module = packager()
        with tempfile.TemporaryDirectory() as temp:
            rootfs = pathlib.Path(temp) / "rootfs.tar.gz"
            self._write_init_tar(rootfs, include_loader=False)
            with self.assertRaisesRegex(ValueError, "P44_INIT_INTERPRETER_MISSING"):
                module.verify_bootable_proto2_rootfs(rootfs)
            self._write_init_tar(rootfs, include_init=False)
            with self.assertRaisesRegex(ValueError, "P44_INIT_MISSING"):
                module.verify_bootable_proto2_rootfs(rootfs)

    def test_native_builder_checks_real_init_chroot_execution(self):
        rootfs = read("scripts/build-proto2-p44-rootfs.sh")
        self.assertIn('chroot "$out" /sbin/init --version', rootfs)
        self.assertIn("P44_INIT_NATIVE_ARM64_CHROOT_EXEC_PASS", rootfs)

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
