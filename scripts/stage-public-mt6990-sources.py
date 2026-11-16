#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Stage SHA-pinned *public text sources* for an independent MT6990 kernel.

This is a source acquisition step, NOT a complete kernel, P25 or boot proof.
It never downloads firmware or writes to a device. Source rights remain with
their respective copyright holders; obtaining a public blob != redistribution.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import tempfile
import urllib.request

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_MANIFEST = ROOT / "configs/public-mt6990-sources.json"
HEX40 = re.compile(r"[0-9a-f]{40}\Z")
ALLOWED_SOURCE = ("target/linux/mediatek/files-6.18/",
                  "target/linux/mediatek/patches-6.18/",
                  "scripts/lg6851f_mkbootimg_v2.py")
ALLOWED_DEST = ("kernel/", "patches/", "tools/public-donor/")
MAX_BLOB = 524288


def git_blob_sha1(data: bytes) -> str:
    """Git's blob identity, not SHA-256 and not a firmware signature."""
    return hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()


def safe_relative(value: object) -> str:
    if not isinstance(value, str) or "\\" in value or "\0" in value:
        raise ValueError("unsafe path")
    p = PurePosixPath(value)
    if (not value or value.startswith("/") or p.is_absolute() or
            any(x in (".", "..") for x in value.split("/")) or str(p) != value):
        raise ValueError("unsafe relative path")
    return value


def check_manifest(doc: object) -> list[dict]:
    if not isinstance(doc, dict) or doc.get("schema") != 1:
        raise ValueError("unsupported manifest schema")
    if doc.get("donor") != "13179415360/openwrt-mt6990-lg6851f":
        raise ValueError("unexpected donor")
    if not isinstance(doc.get("revision"), str) or not HEX40.fullmatch(doc["revision"]):
        raise ValueError("donor commit must be SHA-1")
    files = doc.get("files")
    if not isinstance(files, list) or not files or len(files) > 50:
        raise ValueError("invalid file list")
    seen_sources, seen_dest = set(), set()
    for item in files:
        if not isinstance(item, dict) or set(item) != {"source", "destination", "git_blob_sha1"}:
            raise ValueError("unexpected manifest file fields")
        source = safe_relative(item["source"])
        destination = safe_relative(item["destination"])
        if not source.startswith(ALLOWED_SOURCE) or not destination.startswith(ALLOWED_DEST):
            raise ValueError("source/destination outside source allowlist")
        if not HEX40.fullmatch(item["git_blob_sha1"]):
            raise ValueError("invalid Git blob identity")
        if source in seen_sources or destination in seen_dest:
            raise ValueError("duplicate source/destination")
        if any(word in source.lower() for word in (".bin", ".img", ".elf", "firmware/", "eeprom", "calibration", "secret")):
            raise ValueError("firmware or private input is forbidden")
        seen_sources.add(source)
        seen_dest.add(destination)
    return files


def retrieve(url: str, max_bytes: int = MAX_BLOB) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "terminal6-public-text-source-stager/1"})
    with urllib.request.urlopen(req, timeout=45) as response:
        data = response.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise ValueError("public source exceeds size limit")
    return data


def stage(doc: dict, destination: Path, fetcher=retrieve) -> dict:
    files = check_manifest(doc)
    if not destination.is_absolute() or destination == Path("/"):
        raise ValueError("destination must be a new absolute directory")
    if destination.exists() or destination.is_symlink():
        raise ValueError("destination exists")
    if not destination.parent.is_dir() or destination.parent.is_symlink():
        raise ValueError("destination parent must be a real directory")
    # Never create paths through an existing symlinked ancestor.
    if any(parent.is_symlink() for parent in destination.parents):
        raise ValueError("symlinked destination ancestor")
    temp = Path(tempfile.mkdtemp(prefix=".mt6990-public-stage-", dir=destination.parent))
    receipt = {"schema": 1, "donor": doc["donor"], "revision": doc["revision"],
               "status": "PUBLIC_TEXT_STAGED_NOT_BOOT_VALIDATED", "files": []}
    try:
        for item in files:
            source = item["source"]
            url = ("https://raw.githubusercontent.com/" + doc["donor"] + "/" +
                   doc["revision"] + "/" + source)
            payload = fetcher(url)
            if not isinstance(payload, bytes) or len(payload) > MAX_BLOB:
                raise ValueError("invalid/oversize donor response")
            payload.decode("utf-8")
            actual = git_blob_sha1(payload)
            if actual != item["git_blob_sha1"]:
                raise ValueError("donor Git blob mismatch: " + source)
            out = temp / item["destination"]
            out.parent.mkdir(parents=True, exist_ok=True)
            with out.open("xb") as f:
                f.write(payload)
            receipt["files"].append({
                "source": source, "destination": item["destination"],
                "git_blob_sha1": actual,
                "sha256": hashlib.sha256(payload).hexdigest(), "bytes": len(payload)})
        (temp / "source-receipt.json").write_text(
            json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        os.replace(temp, destination)
        return receipt
    finally:
        if temp.exists():
            shutil.rmtree(temp)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    doc = json.loads(args.manifest.read_text(encoding="utf-8"))
    receipt = stage(doc, args.output)
    print("PUBLIC_MT6990_TEXT_SOURCE_STAGED", len(receipt["files"]))
    print("KERNEL_P25_BOOT_NOT_PROVEN")


if __name__ == "__main__":
    main()
