"""Host-only checks for the C-unit kernel provenance replay gate."""
import tempfile
import unittest
from pathlib import Path

from scripts.replay_80211s_kernel_source import (
    compare_inventories,
    digest,
    inventory_digest,
    source_inventory,
)


class SourceReplayTests(unittest.TestCase):
    def test_inventory_hash_is_deterministic_and_source_sensitive(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "drivers").mkdir()
            source = root / "drivers" / "clk-mt6990.c"
            source.write_text("vendor original\n", encoding="utf-8")
            first = source_inventory(root)
            self.assertEqual(first, source_inventory(root))
            self.assertEqual(inventory_digest(first), inventory_digest(source_inventory(root)))
            source.write_text("vendor changed\n", encoding="utf-8")
            second = source_inventory(root)
            self.assertNotEqual(inventory_digest(first), inventory_digest(second))
            self.assertNotEqual(digest(source), first["drivers/clk-mt6990.c"])

    def test_kbuild_artifacts_are_not_mistaken_for_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "source.c").write_text("int main(void) { return 0; }\n")
            (root / "source.o").write_bytes(b"compiled")
            (root / ".source.o.cmd").write_text("build recipe")
            (root / ".git").mkdir()
            (root / ".git" / "HEAD").write_text("ref: refs/heads/main\n")
            (root / "include" / "generated").mkdir(parents=True)
            (root / "include" / "generated" / "autoconf.h").write_text("generated")
            inventory = source_inventory(root)
            self.assertEqual(set(inventory), {"source.c"})

    def test_comparison_reports_all_three_failure_classes(self):
        a = {"same.c": "a", "changed.h": "old", "vendor.dts": "1"}
        b = {"same.c": "a", "changed.h": "new", "surprise.c": "2"}
        self.assertEqual(
            compare_inventories(a, b),
            {
                "missing_from_replay": ["vendor.dts"],
                "unexpected_in_replay": ["surprise.c"],
                "content_mismatch": ["changed.h"],
            },
        )

    def test_manifest_is_independent_of_map_insertion_order(self):
        self.assertEqual(
            inventory_digest({"b": "2", "a": "1"}),
            inventory_digest({"a": "1", "b": "2"}),
        )


if __name__ == "__main__":
    unittest.main()
