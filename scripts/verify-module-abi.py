#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Reject mismatched P44 modules without changing kernel, P44, or hardware."""
import argparse
from pathlib import Path
import subprocess

def validate(release_file: Path, module_tree: Path, symvers: Path, system_map: Path) -> None:
    release = release_file.read_text().strip()
    if not release or "/" in release or ".." in release:
        raise SystemExit("INVALID_KERNEL_RELEASE")
    if not symvers.is_file() or symvers.stat().st_size == 0:
        raise SystemExit("MODULE_SYMVERS_MISSING")
    if not system_map.is_file() or system_map.stat().st_size == 0:
        raise SystemExit("SYSTEM_MAP_MISSING")
    root = module_tree / "lib" / "modules"
    dirs = list(root.iterdir()) if root.is_dir() else []
    if [d.name for d in dirs] != [release]:
        raise SystemExit("MODULE_ABI_RELEASE_DIRECTORY_MISMATCH")
    modules = sorted(dirs[0].rglob("*.ko"))
    if not modules:
        raise SystemExit("SAME_BUILD_MODULES_MISSING")
    for module in modules:
        p = subprocess.run(["modinfo", "-F", "vermagic", str(module)],
                           capture_output=True, text=True, check=True)
        actual = p.stdout.strip().split(" ", 1)[0]
        if actual != release:
            raise SystemExit(f"VERMAGIC_MISMATCH {module.name}: {actual} != {release}")
    print(f"TERMINAL6_SAME_BUILD_MODULE_ABI_PASS release={release} modules={len(modules)}")
    print("P44_INSTALL_AND_LIVE_INSMOD_NOT_TESTED")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release", required=True, type=Path)
    parser.add_argument("--modules", required=True, type=Path)
    parser.add_argument("--symvers", required=True, type=Path)
    parser.add_argument("--system-map", required=True, type=Path)
    a = parser.parse_args()
    validate(a.release, a.modules, a.symvers, a.system_map)
