#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Overlay SHA-verified, public OSS MT6990 sources into a clean Linux tree.

Fail on conflicts rather than silently taking private board/kernel snapshots.
Selected patches are from one pinned public OpenWrt donor revision. This
prepares a build *candidate*, not a hardware compatible Debian P25.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

CORE_PATCHES = [
    "969-arm64-dts-mediatek-add-mt6990-soc.patch",
    "970-clk-mediatek-mt6990-basic-clock-providers.patch",
    "823-mmc-mtk-sd-add-mt6990-compatible.patch",
]
NETWORK_PATCHES = [
    "973-phy-mediatek-add-mt6990-sgmii.patch",
    "972-net-ethernet-mediatek-add-mt6990-support.patch",
    "972a-net-ethernet-mediatek-register-mt6990.patch",
    "974-net-pcs-mtk-lynxi-add-mt6990-variant.patch",
]


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def verify_stage(stage: Path) -> tuple[list[dict], dict]:
    if not stage.is_dir() or stage.is_symlink():
        raise ValueError("public source stage must be a real directory")
    receipt_file = stage / "source-receipt.json"
    if receipt_file.is_symlink():
        raise ValueError("symlink receipt")
    doc = json.loads(receipt_file.read_text())
    if doc.get("status") != "PUBLIC_TEXT_STAGED_NOT_BOOT_VALIDATED":
        raise ValueError("source receipt not verified")
    items = doc.get("files", [])
    if len(items) != 16 or len({x["destination"] for x in items}) != len(items):
        raise ValueError("incomplete/duplicate public donor inputs")
    for entry in items:
        dest = Path(entry["destination"])
        if dest.is_absolute() or ".." in dest.parts:
            raise ValueError("unsafe donor path")
        p = stage / dest
        if not p.is_file() or p.is_symlink() or sha(p.read_bytes()) != entry["sha256"]:
            raise ValueError("source receipt mismatch: " + str(dest))
    return items, doc


def apply(stage: Path, kernel: Path, scope: str) -> dict:
    items, doc = verify_stage(stage)
    if scope not in ("core", "network"):
        raise ValueError("unsupported scope")
    if not kernel.is_dir() or kernel.is_symlink() or not (kernel / ".git").exists():
        raise ValueError("kernel must be a git worktree")
    for marker in ("Kconfig",):
        if not (kernel / "drivers/clk/mediatek" / marker).is_file():
            raise ValueError("Linux source tree incomplete")
    if subprocess.run(["git", "-C", str(kernel), "status", "--porcelain"],
                      check=True, capture_output=True).stdout.strip():
        raise ValueError("kernel checkout must start clean")
    copies = []
    for entry in items:
        destination = entry["destination"]
        if not destination.startswith("kernel/"):
            continue
        src = stage / destination
        target = kernel / destination[len("kernel/"):]
        if target.exists() or target.is_symlink():
            if target.is_symlink() or sha(target.read_bytes()) != entry["sha256"]:
                raise ValueError("kernel already contains a different file: " + str(target))
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, target)
        copies.append(destination)
    patches = CORE_PATCHES + (NETWORK_PATCHES if scope == "network" else [])
    for p in patches:
        source = stage / "patches" / p
        if not source.is_file():
            raise ValueError("required pinned public patch missing: " + p)
        patch_text = source.read_text()
        if p == "823-mmc-mtk-sd-add-mt6990-compatible.patch":
            # The donor's third hunk forces an LG6851F fixed-rail OCR.
            # The Air6 eMMC rail is board-specific; never port that hunk.
            anchor = "@@ -3042"
            if patch_text.count(anchor) != 1 or "LG6851F board has fixed rails" not in patch_text:
                raise ValueError("donor MMC patch structure changed")
            patch_text = patch_text.split(anchor, 1)[0]
        cmd = ["git", "-C", str(kernel), "apply", "--recount"]
        check = subprocess.run(cmd + ["--check", "-"], input=patch_text,
                               capture_output=True, text=True)
        if check.returncode:
            raise RuntimeError("kernel patch not applicable: " + p + "\n" + check.stderr[-1200:])
        subprocess.run(cmd + ["-"], input=patch_text, check=True, text=True)
    return {"schema": 1, "scope": scope, "source_revision": doc["revision"],
            "status": "PUBLIC_KERNEL_PATCHES_APPLIED_NOT_BUILT",
            "copied_source_files": copies, "patches": patches,
            "kernel_git_revision": subprocess.check_output(
                ["git", "-C", str(kernel), "rev-parse", "HEAD"], text=True).strip()}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source-stage",required=True,type=Path)
    p.add_argument("--kernel-tree",required=True,type=Path)
    p.add_argument("--scope",choices=("core","network"),default="core")
    p.add_argument("--receipt",required=True,type=Path)
    a=p.parse_args()
    if not a.receipt.is_absolute() or a.receipt.exists() or a.receipt.is_symlink():
        p.error("new absolute receipt path required")
    report=apply(a.source_stage,a.kernel_tree,a.scope)
    a.receipt.write_text(json.dumps(report,indent=2,sort_keys=True)+"\n")
    print(report["status"],len(report["copied_source_files"]),len(report["patches"]))


if __name__=="__main__":
    main()
