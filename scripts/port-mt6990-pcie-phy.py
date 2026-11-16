#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Strictly replay the public MT6980/MT6990 PCIe PHY donor hunks on Linux 6.18.63.

The donor patch has a stale hunk location at line 110, and GNU patch may
reject even otherwise identical context. This replay finds every complete
original hunk uniquely in the exact pinned Linux blob, with NO fuzzy matching
or partial context. It fails closed if upstream changes, hunks overlap, or the
source/patch no longer matches the authorized SHA.
"""
from pathlib import Path
import hashlib
import subprocess
import sys

SOURCE_GIT_BLOB = "a2f69d6c72f0808b3b9cd4440e319a2b5b9d5315"
DONOR_PATCH_GIT_BLOB = "6ad2c782ede17eec568ca07b8349379262730a9d"
EXPECTED_HUNKS = 8

def sha_blob(path: Path) -> str:
    return subprocess.check_output(["git", "hash-object", "--", str(path)], text=True).strip()

def parse_hunks(raw: str) -> list[list[str]]:
    hunks: list[list[str]] = []
    active: list[str] | None = None
    for line in raw.splitlines():
        if line.startswith("@@ -"):
            active = []
            hunks.append(active)
        elif active is not None:
            if line.startswith(("+", "-", " ")):
                active.append(line)
            elif line.startswith("\\ No newline"):
                raise ValueError("newline markers not accepted")
            elif line.startswith("@@"):
                raise ValueError("unsupported diff hunk syntax")
            else:
                raise ValueError("unexpected post-hunk line: " + line[:40])
    if len(hunks) != EXPECTED_HUNKS or not all(hunks):
        raise ValueError("wrong number of PCIe PHY donor hunks")
    return hunks

def transform(source: str, patch: str) -> str:
    before = source.splitlines()
    out: list[str] = []
    cursor = 0
    for number, hunk in enumerate(parse_hunks(patch), start=1):
        old = [s[1:] for s in hunk if s[0] in " -"]
        new = [s[1:] for s in hunk if s[0] in " +"]
        if not old or not new or old == new:
            raise ValueError(f"empty/unchanged hunk {number}")
        positions = [i for i in range(cursor, len(before) - len(old) + 1)
                     if before[i:i + len(old)] == old]
        if len(positions) != 1:
            raise ValueError(f"donor hunk {number} matches {len(positions)} times")
        pos = positions[0]
        out.extend(before[cursor:pos])
        out.extend(new)
        cursor = pos + len(old)
    out.extend(before[cursor:])
    if not source.endswith("\n"):
        raise ValueError("expected newline-terminated pinned source")
    return "\n".join(out) + "\n"

def main() -> None:
    if len(sys.argv) != 3:
        raise SystemExit("usage: port-mt6990-pcie-phy.py PUBLIC_PATCH PINNED_LINUX_PHY_SOURCE")
    patch, source = (Path(s) for s in sys.argv[1:])
    if patch.is_symlink() or source.is_symlink() or not patch.is_file() or not source.is_file():
        raise SystemExit("PCIe PHY input must be regular non-symlink files")
    if sha_blob(patch) != DONOR_PATCH_GIT_BLOB:
        raise SystemExit("PUBLIC_PCIE_PHY_DONOR_PATCH_IDENTITY_FAIL")
    if sha_blob(source) != SOURCE_GIT_BLOB:
        raise SystemExit("LINUX_6_18_63_PCIE_PHY_SOURCE_IDENTITY_FAIL")
    result = transform(source.read_text(), patch.read_text())
    if 'mediatek,mt6980-pcie-phy' not in result or "mtk_6980_phy_init" not in result:
        raise SystemExit("PCIE_PHY_MT6980_DRIVER_MISSING")
    source.write_text(result)
    print("PUBLIC_MT6990_PCIE_PHY_EXACT_CONTEXT_8_HUNKS_PASS")
    print("PUBLIC_PCIE_PHY_SOURCE_SHA256=" + hashlib.sha256(source.read_bytes()).hexdigest())

if __name__ == "__main__":
    main()
