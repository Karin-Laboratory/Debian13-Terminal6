#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Build 32MiB unsigned Android boot-v2 from explicitly approved external inputs.

The vendor64 prefix and device-specific load addresses are separate inputs,
never inferred or supplied from proprietary images. Never signs/flashes.
"""
from pathlib import Path
import argparse
import gzip
import hashlib
import json
import struct

SIZE = 32*1024*1024
PAGE = 2048
LIMIT = 35*1024*1024
MAGIC = b"ANDROID!"
FDT = b"\xd0\x0d\xfe\xed"

def align(n):
    return (n + PAGE - 1)//PAGE*PAGE

def produce(image_gz, dtb, vendor64, kernel_addr, tags_addr, cmdline):
    if len(vendor64) != 64 or not dtb.startswith(FDT):
        raise ValueError("vendor64/DTB input invalid")
    dtb_size = struct.unpack_from(">I",dtb,4)[0]
    if dtb_size < 40 or dtb_size > len(dtb):
        raise ValueError("FDT totalsize invalid")
    image = gzip.decompress(image_gz)
    if len(image) < 64 or image[56:60] != b"ARM\x64" or len(image) >= LIMIT:
        raise ValueError("invalid ARM64 Image or LK output >35MiB")
    if not cmdline.isascii() or len(cmdline.encode()) > 511:
        raise ValueError("cmdline must fit boot-v2 header")
    section = vendor64 + dtb
    end = PAGE+align(len(image_gz))+align(len(section))
    if end >= SIZE - 8192 - 262144:
        raise ValueError("image exceeds 32MiB with signing headroom")
    header = bytearray(PAGE)
    header[:8] = MAGIC
    struct.pack_into("<I",header,8,len(image_gz))
    struct.pack_into("<I",header,12,kernel_addr)
    struct.pack_into("<I",header,20,0)
    struct.pack_into("<I",header,24,0)
    struct.pack_into("<I",header,32,tags_addr)
    struct.pack_into("<I",header,36,PAGE)
    struct.pack_into("<I",header,40,2)
    header[64:64+len(cmdline)] = cmdline.encode()
    struct.pack_into("<I",header,1644,1660)
    struct.pack_into("<I",header,1648,len(section))
    sha1 = hashlib.sha1()
    for part in (image_gz,b"",b"",b"",section):
        sha1.update(part)
        sha1.update(struct.pack("<I",len(part)))
    header[576:608] = sha1.digest().ljust(32,b"\0")
    output = bytearray(header)
    for part in (image_gz,section):
        output.extend(part)
        output.extend(bytes(align(len(part))-len(part)))
    output.extend(bytes(SIZE-len(output)))
    return bytes(output), {"image_uncompressed":len(image),"image_gzip":len(image_gz),
      "dtb_bytes":len(dtb),"p25_bytes":len(output),"p25_sha256":hashlib.sha256(output).hexdigest(),
      "status":"UNSIGNED_STRUCTURAL_CANDIDATE_NOT_LK_VERIFIED","signed":False}

def main():
    ap=argparse.ArgumentParser()
    for name in ("image-gz","dtb","vendor64","output"):
        ap.add_argument("--"+name,required=True,type=Path)
    ap.add_argument("--kernel-addr",required=True,type=lambda s:int(s,0))
    ap.add_argument("--tags-addr",required=True,type=lambda s:int(s,0))
    ap.add_argument("--cmdline",default="console=ttyS0,115200n8 root=/dev/mmcblk0p44 rootfstype=ext4 rootwait rw")
    args=ap.parse_args()
    if args.output.exists() or args.output.is_symlink():
        ap.error("refusing existing output")
    blob, receipt = produce(args.image_gz.read_bytes(),args.dtb.read_bytes(),
                            args.vendor64.read_bytes(),args.kernel_addr,args.tags_addr,args.cmdline)
    with args.output.open("xb") as f:
        f.write(blob)
    print(json.dumps(receipt,sort_keys=True))
if __name__=="__main__":main()
