#!/usr/bin/env python3
"""Fail-closed, offline source-replay gate for the C-unit 802.11s kernel.

Run on the private build host. Never publish the private tree or generated JSON.
A successful old artifact checksum is NOT evidence of source reproducibility.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile
import tempfile

from scripts.verify_80211s_config import verify


# Ignore Kbuild output, not vendor source. Keep all .c/.h/Kconfig/DT files.
EXCLUDE_DIRS = {".git", ".tmp_versions", "__pycache__"}
EXCLUDE_PATH_PREFIXES = (
    "include/generated/", "include/config/", "arch/arm64/include/generated/",
    "arch/arm64/kernel/vdso/", "arch/arm64/kernel/vdso32/",
)
EXCLUDE_FILES = {
    ".config", ".config.old", "Module.symvers", "System.map", "vmlinux",
    "vmlinux.o", "modules.order", "modules.builtin", "modules.builtin.modinfo",
    "modules.builtin.ranges", "kernel.release", ".version", ".vmlinux.cmd",
}
EXCLUDE_SUFFIXES = (".o", ".ko", ".a", ".cmd", ".d", ".mod", ".mod.c",
                    ".dtb", ".dtbo", ".pyc", ".symtypes")


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def source_inventory(root: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    for parent, dirs, files in os.walk(root, followlinks=False):
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
        for name in files:
            p = Path(parent) / name
            rel = p.relative_to(root).as_posix()
            if (rel.startswith(EXCLUDE_PATH_PREFIXES) or
                    name in EXCLUDE_FILES or name.startswith(".tmp_") or
                    name.endswith(EXCLUDE_SUFFIXES)):
                continue
            if p.is_symlink():
                result[rel] = "symlink:" + os.readlink(p)
            elif p.is_file():
                result[rel] = digest(p)
    return dict(sorted(result.items()))


def inventory_digest(inventory: dict[str, str]) -> str:
    encoded = json.dumps(inventory, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def compare_inventories(expected: dict[str, str], actual: dict[str, str]) -> dict[str, list[str]]:
    a, b = set(expected), set(actual)
    return {
        "missing_from_replay": sorted(a - b),
        "unexpected_in_replay": sorted(b - a),
        "content_mismatch": sorted(k for k in a & b if expected[k] != actual[k]),
    }


def replay_tarball(tar: Path, output: Path) -> Path:
    # Never extract untrusted archives without the stdlib data filter.
    with tarfile.open(tar, "r:*") as archive:
        archive.extractall(output, filter="data")
    entries = [p for p in output.iterdir() if p.is_dir()]
    if len(entries) != 1:
        raise ValueError("expected one top-level kernel source directory")
    return entries[0]


def apply_patches(source: Path, patches: list[Path]) -> None:
    for patch in patches:
        subprocess.run(["git", "-C", str(source), "apply", "--check", str(patch)],
                       check=True)
        subprocess.run(["git", "-C", str(source), "apply", str(patch)], check=True)


def check_source_replay(tar: Path, expected_sha: str, snapshot: Path,
                        patches: list[Path]) -> dict[str, object]:
    actual_sha = digest(tar)
    if actual_sha != expected_sha.lower():
        raise ValueError("upstream archive SHA256 mismatch")
    if not patches:
        raise ValueError("complete ordered vendor+PR9 patch series required")
    with tempfile.TemporaryDirectory(prefix="cunit-kernel-replay-") as tmp:
        replay = replay_tarball(tar, Path(tmp))
        baseline = source_inventory(replay)
        apply_patches(replay, patches)
        expected = source_inventory(snapshot)
        actual = source_inventory(replay)
        differences = compare_inventories(expected, actual)
        return {
            "schema": 1,
            "status": "SOURCE_REPLAY_MATCH" if not any(differences.values()) else "SOURCE_REPLAY_MISMATCH",
            "upstream_archive_sha256": actual_sha,
            "baseline_tree_sha256": inventory_digest(baseline),
            "snapshot_tree_sha256": inventory_digest(expected),
            "replayed_tree_sha256": inventory_digest(actual),
            "patch_series": [{"file": p.name, "sha256": digest(p)} for p in patches],
            "differences": differences,
        }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--upstream-tar", type=Path, required=True)
    ap.add_argument("--upstream-sha256", required=True)
    ap.add_argument("--private-tree", type=Path, required=True)
    ap.add_argument("--patch", type=Path, action="append", required=True,
                    help="ordered vendor/board patches first, PR #9 last; repeat")
    ap.add_argument("--final-config", type=Path, required=True)
    ap.add_argument("--cc", type=Path, required=True)
    ap.add_argument("--ld", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True,
                    help="owner-private result JSON, never commit")
    args = ap.parse_args()
    result: dict[str, object] = {
        "status": "BLOCKED",
        "scope": "source replay + static config only; no build or hardware validation",
    }
    try:
        if not args.private_tree.is_dir():
            raise ValueError("private source tree does not exist")
        for p in [args.upstream_tar, *args.patch, args.final_config, args.cc, args.ld]:
            if not p.is_file():
                raise ValueError(f"missing input: {p.name}")
        if args.patch[-1].name != "0001-mt7996-eeprom-calfree-timeout.patch":
            raise ValueError("last patch must be PR #9 calibration/timeout patch")
        result.update(check_source_replay(args.upstream_tar, args.upstream_sha256,
                                          args.private_tree, args.patch))
        result["final_config_sha256"] = digest(args.final_config)
        result["compiler_sha256"] = digest(args.cc)
        result["linker_sha256"] = digest(args.ld)
        result["mesh_input"] = verify(args.final_config, args.private_tree)
        result["pass"] = (result["status"] == "SOURCE_REPLAY_MATCH" and
                          result["mesh_input"]["pass"])
        if not result["pass"]:
            result["status"] = "BLOCKED"
    except (OSError, ValueError, subprocess.CalledProcessError, tarfile.TarError) as exc:
        result["status"] = "BLOCKED"
        result["pass"] = False
        result["failure"] = f"{type(exc).__name__}: {exc}"
    # Treat report as private: includes possible vendor filenames in differences.
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n",
                           encoding="utf-8")
    os.chmod(args.output, 0o600)
    print(f"CUNIT_SOURCE_REPLAY={result['status']}")
    print(f"PRIVATE_REPORT={args.output}")
    return 0 if result["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
