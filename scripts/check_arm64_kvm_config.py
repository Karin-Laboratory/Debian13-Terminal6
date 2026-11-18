#!/usr/bin/env python3
"""Fail-closed validation of an ARM64 Linux .config for KVM host support."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


def read_config(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        match = re.fullmatch(r"(CONFIG_[A-Z0-9_]+)=(.*)", line)
        if match:
            values[match.group(1)] = match.group(2)
            continue
        match = re.fullmatch(r"# (CONFIG_[A-Z0-9_]+) is not set", line)
        if match:
            values[match.group(1)] = "n"
    return values


def validate(values: dict[str, str]) -> list[str]:
    errors: list[str] = []
    if values.get("CONFIG_ARM64") != "y":
        errors.append("CONFIG_ARM64 must be y")
    if values.get("CONFIG_VIRTUALIZATION") != "y":
        errors.append("CONFIG_VIRTUALIZATION must be y")
    if values.get("CONFIG_KVM") != "y":
        errors.append("CONFIG_KVM must be built-in (y)")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("config", type=Path, help="Linux kernel .config")
    args = parser.parse_args()
    try:
        errors = validate(read_config(args.config))
    except OSError as exc:
        print(f"ERROR: cannot read config: {exc}", file=sys.stderr)
        return 2
    if errors:
        for error in errors:
            print(f"FAIL: {error}", file=sys.stderr)
        return 1
    print("PASS: ARM64 KVM host support is enabled in the kernel config")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
