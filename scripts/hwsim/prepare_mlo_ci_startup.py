#!/usr/bin/env python3
"""Disable hostap's optional wlan0 D-Bus registration only in disposable CI hwsim.

A system-level D-Bus integration is not required by the EHT MLD socket tests.
This never runs on the C unit. The source revision/pattern must match exactly.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import subprocess

PINNED = "f1e9b5086718ad567dc40e3d5a1456534d51749f"
ORIGINAL = 'DBUSARG="-u"'
REPLACEMENT = 'DBUSARG="" # C-unit isolated CI: skip optional system D-Bus claim'


def disable_optional_dbus(text: str) -> str:
    if text.count(ORIGINAL) != 1:
        raise ValueError("expected exactly one optional wlan0 D-Bus assignment")
    if 'if [ $i = "0" ]' not in text:
        raise ValueError("unexpected upstream D-Bus activation context")
    return text.replace(ORIGINAL, REPLACEMENT, 1)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--hostap-tree", type=Path, required=True)
    args = p.parse_args()
    root = args.hostap_tree.resolve(strict=True)
    version = subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"],
                             text=True, capture_output=True, check=True).stdout.strip()
    if version != PINNED:
        raise SystemExit("BLOCKED: unexpected upstream hostap version")
    file = root / "tests/hwsim/start.sh"
    original = file.read_text()
    try:
        updated = disable_optional_dbus(original)
    except ValueError:
        raise SystemExit("BLOCKED: upstream D-Bus option context differs") from None
    file.write_text(updated)
    print("CUNIT_MLO_CI_OPTIONAL_DBUS_DISABLED=true")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
