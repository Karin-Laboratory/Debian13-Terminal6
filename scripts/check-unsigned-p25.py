#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Validate only Android boot-v2 candidate structure and 32MiB size; never sign or flash."""
import argparse
from pathlib import Path
import struct

P25_BYTES = 32 * 1024 * 1024

def inspect(data):
    if len(data) != P25_BYTES:
        raise ValueError(f"expected {P25_BYTES} bytes, got {len(data)}")
    if data[:8] != b"ANDROID!":
        raise ValueError("Android boot magic missing")
    kernel_size = struct.unpack_from("<I", data, 8)[0]
    page_size = struct.unpack_from("<I", data, 36)[0]
    version = struct.unpack_from("<I", data, 40)[0]
    if page_size not in (2048, 4096, 8192, 16384):
        raise ValueError("unexpected page size")
    if version != 2:
        raise ValueError("expected boot header v2")
    if not 0 < kernel_size < P25_BYTES - page_size:
        raise ValueError("invalid kernel size")
    return {"kernel_size": kernel_size, "page_size": page_size, "header_version": version}

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("image", type=Path)
    args = parser.parse_args()
    print("UNSIGNED_P25_STRUCTURE_PASS", inspect(args.image.read_bytes()))
    print("Header check does not establish LK bootability or compatibility")
