"""Synthetic, host-only tests of private source reconstruction."""
import tarfile
import tempfile
import unittest
from pathlib import Path

from scripts.reconstruct_80211s_vendor_patch import reconstruct
from scripts.replay_80211s_kernel_source import digest


class VendorReconstructionTests(unittest.TestCase):
    def test_reconstructs_private_patch_and_replays_pr9(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            upstream = root / "linux-6.18.63"
            directory = upstream / "drivers/clk/mediatek"
            directory.mkdir(parents=True)
            (directory / "common.c").write_text("original\n")
            archive = root / "upstream.tar"
            with tarfile.open(archive, "w") as out:
                out.add(upstream, arcname=upstream.name)

            snapshot = root / "owner-snapshot"
            vendor_dir = snapshot / "drivers/clk/mediatek"
            vendor_dir.mkdir(parents=True)
            (vendor_dir / "common.c").write_text("pr9-modified\n")
            (vendor_dir / "clk-mt6990.c").write_text("vendor-src\n")
            pr9 = root / "0001-mt7996-eeprom-calfree-timeout.patch"
            pr9.write_text(
                "--- a/drivers/clk/mediatek/common.c\n"
                "+++ b/drivers/clk/mediatek/common.c\n"
                "@@ -1 +1 @@\n"
                "-original\n"
                "+pr9-modified\n"
            )
            output = root / "private-patches"
            receipt = reconstruct(archive, digest(archive), snapshot, pr9, output)
            self.assertEqual(receipt["status"], "PRIVATE_SOURCE_REPLAY_MATCH")
            self.assertFalse(receipt["publication_allowed"])
            self.assertEqual(receipt["snapshot_source_tree_sha256"],
                             receipt["replay_source_tree_sha256"])
            self.assertTrue((output / "PRIVATE-MT6990-vendor-board-source.patch").is_file())
            self.assertTrue((output / "PRIVATE-MT6990-source-manifest.json").is_file())
            with self.assertRaises(ValueError):
                reconstruct(archive, digest(archive), snapshot, pr9, output)

    def test_complete_private_snapshot_includes_pr9_without_separating_provenance(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            upstream = root / "linux-6.18.63"
            directory = upstream / "drivers/clk/mediatek"
            directory.mkdir(parents=True)
            (directory / "common.c").write_text("original\n")
            archive = root / "upstream.tar"
            with tarfile.open(archive, "w") as out:
                out.add(upstream, arcname=upstream.name)

            snapshot = root / "owner-snapshot"
            vendor_dir = snapshot / "drivers/clk/mediatek"
            vendor_dir.mkdir(parents=True)
            (vendor_dir / "common.c").write_text("pr9-and-vendor-modified\n")
            (vendor_dir / "clk-mt6990.c").write_text("vendor-src\n")
            pr9 = root / "0001-mt7996-eeprom-calfree-timeout.patch"
            pr9.write_text("not applicable to the changed source context\n")
            output = root / "private-patches"
            receipt = reconstruct(
                archive, digest(archive), snapshot, pr9, output,
                include_pr9_in_private_snapshot=True)
            self.assertEqual(receipt["status"], "PRIVATE_SOURCE_REPLAY_MATCH")
            self.assertFalse(receipt["publication_allowed"])
            self.assertFalse(receipt["pr9_patch_separate_reverse_apply"])
            self.assertIn("not separated", receipt["scope"])
            self.assertEqual(receipt["snapshot_source_tree_sha256"],
                             receipt["replay_source_tree_sha256"])
            self.assertTrue((output / "PRIVATE-MT6990-complete-source-snapshot.patch").is_file())
            self.assertFalse((output / "PRIVATE-MT6990-vendor-board-source.patch").exists())

    def test_refuses_wrong_tar_digest(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            file = root / "tar"
            file.write_bytes(b"not a kernel tar")
            snapshot = root / "source"
            snapshot.mkdir()
            patch = root / "pr9.patch"
            patch.write_text("bogus")
            with self.assertRaisesRegex(ValueError, "SHA mismatch"):
                reconstruct(file, "0" * 64, snapshot, patch, root / "private")


if __name__ == "__main__":
    unittest.main()
