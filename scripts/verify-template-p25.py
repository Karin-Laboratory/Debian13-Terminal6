#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Independent structural and payload verifier for an unsigned P25 candidate."""
from pathlib import Path
import argparse
import gzip
import hashlib
import json
import struct

SIZE=33554432
PAGE=2048
FDT=b"\xd0\x0d\xfe\xed"

def align(n):
    return (n+PAGE-1)//PAGE*PAGE

def verify(image, kernel_gz, dtb, initramfs, template):
    if len(image)!=SIZE or len(template)!=SIZE or image[:8]!=b"ANDROID!":
        raise ValueError("bad size/magic")
    if struct.unpack_from("<II",image,36)!=(PAGE,2) or struct.unpack_from("<I",image,1644)[0]!=1660:
        raise ValueError("bad header version/page/header size")
    if image[:8]!=template[:8] or image[12:16]!=template[12:16] or image[32:36]!=template[32:36]:
        raise ValueError("LK load addresses changed from template")
    sizes=[struct.unpack_from("<I",image,ofs)[0] for ofs in (8,16,24,1632,1648)]
    kn,rd,second,recovery,dtbsz=sizes
    if (rd,second,recovery)!=(0,0,0) or kn!=len(kernel_gz) or dtbsz!=64+len(dtb):
        raise ValueError("section lengths mismatch")
    kp=PAGE
    dp=PAGE+align(kn)
    vend=template[PAGE+align(struct.unpack_from("<I",template,8)[0]):]
    if image[kp:kp+kn]!=kernel_gz or image[dp:dp+64]!=vend[:64] or image[dp+64:dp+dtbsz]!=dtb:
        raise ValueError("section bytes mismatch")
    if dtb[:4]!=FDT or struct.unpack_from(">I",dtb,4)[0]>len(dtb):
        raise ValueError("invalid embedded DTB")
    end=dp+align(dtbsz)
    if end>=SIZE-8192-262144 or any(image[end:]):
        raise ValueError("unsigned tail/headroom invalid")
    computed=hashlib.sha1()
    for part in (kernel_gz,b"",b"",b"",image[dp:dp+dtbsz]):
        computed.update(part);computed.update(struct.pack("<I",len(part)))
    if image[576:608]!=computed.digest().ljust(32,b"\0"):
        raise ValueError("boot image SHA-1 id mismatch")
    raw=gzip.decompress(kernel_gz)
    if raw[:4]!=b"MZ\x00\x00" or len(raw)>=35*1024*1024 or raw.count(initramfs)!=1:
        raise ValueError("kernel decompression or linked initramfs invalid")
    if b"/dev/mmcblk0p44" not in gzip.decompress(initramfs):
        raise ValueError("initramfs does not select P44")
    return {"status":"UNSIGNED_P25_INDEPENDENT_STRUCTURAL_PASS",
            "p25_bytes":len(image),"p25_sha256":hashlib.sha256(image).hexdigest(),
            "dtb_bytes":len(dtb),"kernel_image_bytes":len(raw),
            "hardware_boot":"NOT_TESTED","signing":"NOT_EXECUTED"}

def main():
    ap=argparse.ArgumentParser()
    for v in ("p25","kernel-gz","dtb","initramfs-cpio-gz","template"):
        ap.add_argument("--"+v,type=Path,required=True)
    a=ap.parse_args()
    result=verify(a.p25.read_bytes(),a.kernel_gz.read_bytes(),a.dtb.read_bytes(),
                  a.initramfs_cpio_gz.read_bytes(),a.template.read_bytes())
    print(json.dumps(result,sort_keys=True))
if __name__=="__main__": main()
