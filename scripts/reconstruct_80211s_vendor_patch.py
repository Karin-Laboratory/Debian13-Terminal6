#!/usr/bin/env python3
"""Reconstruct a PRIVATE vendor/board source patch from an owner's kernel snapshot.

The result is not automatically redistributable and does not establish vendor
authorship. Keep both generated outputs outside Git and owner-private.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

from scripts.replay_80211s_kernel_source import (
    apply_patches, compare_inventories, digest, inventory_digest,
    replay_tarball, source_inventory,
)


def git(source: Path, *args: str, capture: bool = False) -> str:
    command = ["git", "-C", str(source), *args]
    proc = subprocess.run(command, check=True, text=True,
                          stdout=subprocess.PIPE if capture else subprocess.DEVNULL,
                          stderr=subprocess.PIPE)
    return proc.stdout if capture else ""


def match_source_files(snapshot: Path, destination: Path) -> None:
    """Synchronize source files, never following owner tree symlinks."""
    actual, existing = source_inventory(snapshot), source_inventory(destination)
    for rel in sorted(existing.keys() - actual.keys()):
        (destination / rel).unlink()
    for rel in sorted(actual):
        src, dest = snapshot / rel, destination / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.is_file() or dest.is_symlink():
            dest.unlink()
        if src.is_symlink():
            dest.symlink_to(os.readlink(src))
        else:
            shutil.copy2(src, dest)


def check_private_output(output: Path) -> None:
    if output.is_symlink():
        raise ValueError("refusing symlink output directory")
    if any((p / ".git").exists() for p in (output, *output.parents)):
        raise ValueError("private output directory must not be inside a Git checkout")
    if output.exists() and (not output.is_dir() or any(output.iterdir())):
        raise ValueError("private output directory must be an empty directory")


def reconstruct(upstream_tar: Path, expected_sha: str, snapshot: Path,
                pr9_patch: Path, output: Path) -> dict[str, object]:
    if digest(upstream_tar) != expected_sha:
        raise ValueError("upstream Linux tar SHA mismatch")
    if not snapshot.is_dir() or not pr9_patch.is_file():
        raise ValueError("missing owner-private snapshot or PR #9 patch")
    check_private_output(output)
    with tempfile.TemporaryDirectory(prefix="cunit-80211s-reconstruct-") as temp:
        baseline = replay_tarball(upstream_tar, Path(temp))
        git(baseline, "init", "-q")
        git(baseline, "add", "-A")
        git(baseline, "-c", "user.name=CUnit Replay",
            "-c", "user.email=cunit-replay@localhost",
            "commit", "-qm", "upstream tar")
        match_source_files(snapshot, baseline)
        # Owner snapshot already includes PR #9; remove that change so
        # vendor patch and PR #9 patch can be applied independently.
        git(baseline, "apply", "--check", "-R", str(pr9_patch.resolve()))
        git(baseline, "apply", "-R", str(pr9_patch.resolve()))
        git(baseline, "add", "-A")
        vendor_diff = git(baseline, "diff", "--cached",
                          "--binary", "--full-index", capture=True)
        if not vendor_diff.strip():
            raise ValueError("no vendor source delta found")
        with tempfile.TemporaryDirectory(prefix="cunit-80211s-confirm-") as confirm:
            replayed = replay_tarball(upstream_tar, Path(confirm))
            patch = Path(temp) / "vendor-private.patch"
            patch.write_text(vendor_diff, encoding="utf-8")
            apply_patches(replayed, [patch, pr9_patch.resolve()])
            expected_inv = source_inventory(snapshot)
            actual_inv = source_inventory(replayed)
            differences = compare_inventories(expected_inv, actual_inv)
            if any(differences.values()):
                raise ValueError("independent source replay mismatch: " + json.dumps(
                    {key: len(v) for key, v in differences.items()}))
            if "drivers/clk/mediatek/clk-mt6990.c" not in actual_inv:
                raise ValueError("MT6990 clock vendor source is still absent")
            if output.exists():
                os.chmod(output, 0o700)
            else:
                output.mkdir(parents=True, mode=0o700)
            out_patch = output / "PRIVATE-MT6990-vendor-board-source.patch"
            with out_patch.open("x", encoding="utf-8") as f:
                f.write(vendor_diff)
            os.chmod(out_patch, 0o600)
            receipt = {
                "schema": 1,
                "status": "PRIVATE_SOURCE_REPLAY_MATCH",
                "upstream_tar_sha256": digest(upstream_tar),
                "snapshot_source_tree_sha256": inventory_digest(expected_inv),
                "replay_source_tree_sha256": inventory_digest(actual_inv),
                "ordered_patches": [
                    {"name": out_patch.name, "sha256": digest(out_patch),
                     "role": "private_vendor_board"},
                    {"name": pr9_patch.name, "sha256": digest(pr9_patch),
                     "role": "pr9_eeprom_otp"},
                ],
                "publication_allowed": False,
                "scope": "byte-for-byte source replay; no license, build or RF claim",
            }
            out_receipt = output / "PRIVATE-MT6990-source-manifest.json"
            with out_receipt.open("x", encoding="utf-8") as f:
                json.dump(receipt, f, indent=2, sort_keys=True)
                f.write("\n")
            os.chmod(out_receipt, 0o600)
            return receipt


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--upstream-tar", type=Path, required=True)
    parser.add_argument("--upstream-sha256", required=True)
    parser.add_argument("--private-tree", type=Path, required=True)
    parser.add_argument("--pr9-patch", type=Path, required=True)
    parser.add_argument("--private-output-dir", type=Path, required=True)
    parser.add_argument("--ack-private-only", action="store_true", required=True)
    args = parser.parse_args()
    try:
        result = reconstruct(args.upstream_tar, args.upstream_sha256.lower(),
                             args.private_tree, args.pr9_patch, args.private_output_dir)
        print("CUNIT_SOURCE_RECONSTRUCTION=" + result["status"])
        print("PRIVATE_OUTPUT_DIR=" + str(args.private_output_dir))
        return 0
    except (ValueError, OSError, subprocess.CalledProcessError) as exc:
        print("CUNIT_SOURCE_RECONSTRUCTION=BLOCKED; " + str(exc))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
