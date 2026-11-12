#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Preserve a privately verified *unsigned* boot-v2 template's LK header.
Never imports/publishes the template or proprietary vendor64 bytes into git.
"""
from pathlib import Path
import argparse
import gzip
import hashlib
import json
import struct

PAGE=2048
SIZE=33554432
CAP=35*1024*1024
HEADROOM=8192+262144
MAGIC=b"ANDROID!"
FDT=b"\xd0\x0d\xfe\xed"

def sha(data):
    return hashlib.sha256(data).hexdigest()

def align(n):
    return (n+PAGE-1)//PAGE*PAGE

def fields(blob):
    if len(blob)!=SIZE or blob[:8]!=MAGIC:
        raise ValueError("template length/magic invalid")
    page,ver=struct.unpack_from("<II",blob,36)
    if (page,ver)!=(PAGE,2) or struct.unpack_from("<I",blob,1644)[0]!=1660:
        raise ValueError("template boot header layout unsupported")
    n=struct.unpack_from("<I",blob,8)[0]
    rd=struct.unpack_from("<I",blob,16)[0]
    sec=struct.unpack_from("<I",blob,24)[0]
    recovery=struct.unpack_from("<I",blob,1632)[0]
    dtbsz=struct.unpack_from("<I",blob,1648)[0]
    if any((rd,sec,recovery)) or not (64+40<=dtbsz<SIZE):
        raise ValueError("template sections unexpected")
    at=PAGE+align(n)
    old_dtb=blob[at:at+dtbsz]
    if old_dtb[64:68]!=FDT:
        raise ValueError("template vendor64+FDT not found")
    return old_dtb[:64]

def produce(template, image_gz, dtb, cpio_gz, cmdline):
    vendor64=fields(template)
    if not dtb.startswith(FDT) or len(dtb)<40 or struct.unpack_from(">I",dtb,4)[0] not in range(40,len(dtb)+1):
        raise ValueError("invalid bare FDT")
    image=gzip.decompress(image_gz)
    if len(image)<64 or image[56:60]!=b"ARM\x64" or len(image)>=CAP:
        raise ValueError("ARM64 Image invalid or LK cap exceeded")
    if image.count(cpio_gz)!=1:
        raise ValueError("built Image must embed exactly one Debian P44 initramfs")
    if b"/dev/mmcblk0p44" not in gzip.decompress(cpio_gz):
        raise ValueError("initramfs does not reference expected P44")
    cmd=cmdline.encode("ascii")
    if len(cmd)>511:
        raise ValueError("kernel cmdline too long")
    payload=vendor64+dtb
    end=PAGE+align(len(image_gz))+align(len(payload))
    if end>=SIZE-HEADROOM:
        raise ValueError("P25 signing headroom insufficient")
    head=bytearray(template[:PAGE])
    head[64:576]=bytes(512)
    head[64:64+len(cmd)]=cmd
    head[608:1632]=bytes(1024)
    for off,n in ((8,len(image_gz)),(16,0),(24,0),(1632,0),(1648,len(payload))):
        struct.pack_into("<I",head,off,n)
    boot_id=hashlib.sha1()
    for part in (image_gz,b"",b"",b"",payload):
        boot_id.update(part);boot_id.update(struct.pack("<I",len(part)))
    head[576:608]=boot_id.digest().ljust(32,b"\0")
    out=bytearray(head)
    for item in (image_gz,payload):
        out+=item
        out+=bytes(align(len(item))-len(item))
    out+=bytes(SIZE-len(out))
    result=bytes(out)
    return result,{"p25_bytes":len(result),"p25_sha256":sha(result),
                   "original_template_sha256":sha(template),"debian_p44_initramfs_sha256":sha(cpio_gz),
                   "image_bytes":len(image),"kernel_gzip_bytes":len(image_gz),
                   "dtb_bytes":len(dtb),"status":"UNSIGNED_P25_TEMPLATE_PRESERVED_NOT_BOOT_VALIDATED",
                   "signing":"NOT_EXECUTED","hardware_boot":"NOT_TESTED"}

def main():
    ap=argparse.ArgumentParser()
    for p in ("template","kernel-gz","dtb","initramfs-cpio-gz","output"):
        ap.add_argument("--"+p,required=True,type=Path)
    ap.add_argument("--template-sha256",required=True)
    ap.add_argument("--cmdline",default="console=ttyS0,115200n8 root=/dev/mmcblk0p44 rootfstype=ext4 rootwait rw")
    a=ap.parse_args()
    for p in (a.template,a.kernel_gz,a.dtb,a.initramfs_cpio_gz):
        if not p.is_absolute() or not p.is_file() or p.is_symlink():
            ap.error("inputs must be absolute regular files")
    if a.output.exists() or a.output.is_symlink() or not a.output.is_absolute():
        ap.error("output must be new absolute path")
    template=a.template.read_bytes()
    if sha(template)!=a.template_sha256:
        ap.error("template SHA mismatch")
    output,rec=produce(template,a.kernel_gz.read_bytes(),a.dtb.read_bytes(),
                       a.initramfs_cpio_gz.read_bytes(),a.cmdline)
    with a.output.open("xb") as f:f.write(output)
    print(json.dumps(rec,sort_keys=True))
if __name__=="__main__":main()
