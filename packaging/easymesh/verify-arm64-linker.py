#!/usr/bin/env python3
"""Inspect AArch64 prplMesh dynamic linking under QEMU-user without starting the daemons."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

BINARIES = ("ieee1905_transport", "beerocks_controller", "beerocks_agent", "beerocks_vendor_message")
INTERPRETER_RE = re.compile(r"\[Requesting program interpreter:\s*(/[^\]]+)\]")
MACHINE_RE = re.compile(r"(?m)^\s*Machine:\s*(.+?)\s*$")


class LoaderCheckError(Exception):
    pass


def parse_machine(output: str) -> None:
    match = MACHINE_RE.search(output)
    if not match or match.group(1) != "AArch64":
        raise LoaderCheckError("expected AArch64 ELF executable")


def parse_interpreter(output: str) -> str:
    match = INTERPRETER_RE.search(output)
    if not match:
        raise LoaderCheckError("ELF interpreter not found (expected dynamically linked executable)")
    interpreter = match.group(1)
    if ".." in Path(interpreter).parts:
        raise LoaderCheckError("invalid interpreter path")
    return interpreter


def inspect(binary: Path, sysroot: Path, stage_lib: Path, qemu: str, run=subprocess.run) -> dict[str, str]:
    """Run only the target dynamic loader --list; NEVER run the prplMesh entry point."""
    if not binary.is_file():
        raise LoaderCheckError(f"missing staged executable: {binary.name}")
    results = []
    for option in ("-h", "-l"):
        try:
            result = run(["readelf", option, str(binary)], check=False,
                         capture_output=True, text=True, timeout=10)
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise LoaderCheckError(f"readelf failed: {exc.__class__.__name__}") from None
        if result.returncode:
            raise LoaderCheckError(f"invalid ELF metadata: {binary.name}")
        results.append(result.stdout)
    parse_machine(results[0])
    interpreter = parse_interpreter(results[1])
    loader = sysroot / interpreter.lstrip("/")
    if not loader.is_file():
        raise LoaderCheckError(f"target interpreter missing in sysroot: {interpreter}")

    paths = [stage_lib, sysroot / "lib/aarch64-linux-gnu",
             sysroot / "usr/lib/aarch64-linux-gnu", sysroot / "lib", sysroot / "usr/lib"]
    command = [qemu, "-L", str(sysroot), str(loader),
               "--library-path", ":".join(str(path) for path in paths),
               "--list", str(binary)]
    try:
        result = run(command, check=False, capture_output=True, text=True, timeout=20,
                     env={"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "LANG": "C", "LC_ALL": "C"})
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise LoaderCheckError(f"QEMU loader inspection failed: {exc.__class__.__name__}") from None
    listing = result.stdout + result.stderr
    if result.returncode or "not found" in listing.lower() or "cannot open shared object file" in listing.lower():
        raise LoaderCheckError(f"unresolved target libraries or loader failure: {binary.name}")
    if "=>" not in listing:
        raise LoaderCheckError(f"no resolved shared-library listing from target loader: {binary.name}")
    return {"binary": binary.name, "interpreter": interpreter, "result": "loader-libraries-resolved"}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", type=Path, required=True, help="private AArch64 prplMesh install prefix")
    parser.add_argument("--sysroot", type=Path, required=True, help="isolated Debian 13 arm64 sysroot")
    parser.add_argument("--qemu", default="qemu-aarch64", help="qemu-aarch64 or qemu-aarch64-static")
    args = parser.parse_args()
    try:
        stage = args.stage.resolve(strict=True)
        sysroot = args.sysroot.resolve(strict=True)
        if not stage.is_dir() or not sysroot.is_dir():
            raise LoaderCheckError("stage and sysroot must be directories")
        if not shutil.which("readelf") or not shutil.which(args.qemu):
            raise LoaderCheckError("readelf and QEMU-user must both be installed")
        results = [inspect(stage / "bin" / name, sysroot, stage / "lib", args.qemu) for name in BINARIES]
    except (OSError, LoaderCheckError) as exc:
        print(f"EASYMESH_ARM64_LOADER=FAIL reason={exc}", file=sys.stderr)
        return 1
    print(json.dumps({"verdict": "loader-only", "runtime_process_started": False,
                      "two_node_ieee1905_verified": False, "binaries": results}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
