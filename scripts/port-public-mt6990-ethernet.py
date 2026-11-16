#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Rebase one SHA-pinned MT6990 Ethernet source patch to Linux 6.18.63.

This is NOT a generic context-free patch tool. Every insertion is restricted
to an exact stable-6.18 location, donor hunk shape, and source hash receipt.
The LG6851F-only assumptions are not silently adopted. A SOURCE-REPLAY PASS
is not a compiled driver or functional Ethernet proof.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re

DONOR_PATCH = "patches/972-net-ethernet-mediatek-add-mt6990-support.patch"
HEAD_FILE = "drivers/net/ethernet/mediatek/mtk_eth_soc.h"
ETH_FILE = "drivers/net/ethernet/mediatek/mtk_eth_soc.c"
EXPECTED_GROUPS = [[6], [1], [1], [12], [55], [6], [5, 11],
                   [3], [3], [14], [39], [1]]


def source_hunks(patch: str):
    hunks = []
    file = None
    hunk = None
    for line in patch.splitlines():
        if line.startswith("+++ b/"):
            file = line[6:]
        if line.startswith("@@ "):
            hunk = {"file": file, "groups": [], "open": []}
            hunks.append(hunk)
            continue
        if hunk is None:
            continue
        if line.startswith("+") and not line.startswith("+++ "):
            hunk["open"].append(line[1:])
        elif hunk["open"]:
            hunk["groups"].append(hunk["open"])
            hunk["open"] = []
    if hunk and hunk["open"]:
        hunk["groups"].append(hunk["open"])
    if ([list(map(len, x["groups"])) for x in hunks] != EXPECTED_GROUPS
            or len(hunks) != 12
            or any(x["file"] != (HEAD_FILE if i < 4 else ETH_FILE)
                   for i, x in enumerate(hunks))):
        raise ValueError("MT6990 Ethernet donor patch changed shape")
    return hunks


def group(hunks, i, j=0):
    return "\n".join(hunks[i]["groups"][j]) + "\n"


def after_once(src: str, needle: str, insert: str):
    if src.count(needle) != 1:
        raise ValueError("ambiguous or missing stable source insertion after: " + needle[:70])
    return src.replace(needle, needle + insert)


def before_once(src: str, needle: str, insert: str):
    if src.count(needle) != 1:
        raise ValueError("ambiguous or missing stable source insertion before: " + needle[:70])
    return src.replace(needle, insert + needle)


def after_regex_once(src: str, pattern: str, insert: str):
    hits = list(re.finditer(pattern, src, re.M))
    if len(hits) != 1:
        raise ValueError("ambiguous or missing stable regex insertion")
    at = hits[0].end()
    return src[:at] + insert + src[at:]


def apply(h: str, c: str, patch: str):
    if "MTK_SOC_MT6990_BIT" in h or "mt6990_reg_map" in c:
        raise ValueError("MT6990 Ethernet patch already integrated")
    H=source_hunks(patch)
    h=after_once(h,"\tMTK_CLK_TOP_NETSYS_WARP_SEL,\n",group(H,0))
    # Preserve the upstream ABI numbering of MTK_GMAC_EEE_BIT where possible.
    h=after_once(h,"\tMTK_GMAC_EEE_BIT,\n",group(H,1))
    h=after_regex_once(h,r"^#define MTK_36BIT_DMA\s+BIT_ULL\(MTK_36BIT_DMA_BIT\)\n",group(H,2))
    h=before_once(h,"struct mtk_tx_dma_desc_info {",group(H,3))
    c=before_once(c,"static const struct mtk_reg_map mt7988_reg_map = {",group(H,4))
    c=after_once(c,'\t"top_netsys_warp_sel",\n',group(H,5))
    c=after_once(c,
        "\t\t   MAC_MCR_BACKOFF_EN | MAC_MCR_BACKPR_EN | MAC_MCR_RX_FIFO_CLR_DIS;\n",
        group(H,6,0))
    c=before_once(c,"static void mtk_mac_link_down(",group(H,6,1))
    # Insert inside the specific link_down function, not another MAC callback.
    func="static void mtk_mac_link_down("
    start=c.index(func)
    end=c.index("\n}\n",start)
    sub=c[start:end]
    sub=after_once(sub,"\t\t\t\t\t   phylink_config);\n",group(H,7))
    c=c[:start]+sub+c[end:]
    # Insert directly before link_up's closing brace.
    start=c.index("static void mtk_mac_link_up(")
    end=c.index("\n}\n",start)
    c=c[:end] + "\n" + group(H,8).rstrip("\n") + c[end:]
    start=c.index("static int mtk_start_dma(")
    end=c.index("\n}\n",start)
    sub=c[start:end]
    sub=after_once(sub,"\t\treturn err;\n\t}\n\n",group(H,9))
    c=c[:start]+sub+c[end:]
    soc=group(H,10)
    # Donor has fields/macros no longer in stable's mtk_soc_data ABI.
    # Preserve declared descriptor sizes, but translate to stable syntax.
    if soc.count("DESC_SIZE(struct mtk_tx_dma_v2)") != 1:
        raise ValueError("donor TX descriptor mapping changed")
    if soc.count("DESC_SIZE(struct mtk_rx_dma)") != 1:
        raise ValueError("donor RX descriptor mapping changed")
    if soc.count("\t.num_tx_queues = 16,") != 1:
        raise ValueError("donor queue count changed; do not guess stable ABI")
    soc=soc.replace("\t\tDESC_SIZE(struct mtk_tx_dma_v2)",
                    "\t\t.desc_size = sizeof(struct mtk_tx_dma_v2)")
    soc=soc.replace("\t\tDESC_SIZE(struct mtk_rx_dma)",
                    "\t\t.desc_size = sizeof(struct mtk_rx_dma)")
    soc=soc.replace("\t.num_tx_queues = 16,\n", "")
    c=before_once(c,"static const struct mtk_soc_data rt5350_data = {",soc)
    c=after_once(c,
      '\t{ .compatible = "mediatek,mt7988-eth", .data = &mt7988_data },\n',
      group(H,11))
    if h.count("MTK_SOC_MT6990_BIT") != 2 or c.count("mt6990_data") < 2:
        raise ValueError("MT6990 rebased source inconsistent")
    return h,c


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--stage",required=True,type=Path)
    p.add_argument("--linux",required=True,type=Path)
    a=p.parse_args()
    if not a.stage.is_dir() or a.stage.is_symlink():
        p.error("valid non-symlink stage required")
    if not a.linux.is_dir() or a.linux.is_symlink():
        p.error("valid non-symlink Linux tree required")
    receipt=json.loads((a.stage/"source-receipt.json").read_text())
    matches=[x for x in receipt.get("files",[]) if x["destination"]==DONOR_PATCH]
    if len(matches)!=1:
        raise ValueError("pinned donor Ethernet patch absent from receipt")
    patch_file=a.stage/DONOR_PATCH
    raw=patch_file.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=matches[0]["sha256"]:
        raise ValueError("Ethernet donor source hash mismatch")
    hp=a.linux/HEAD_FILE
    cp=a.linux/ETH_FILE
    if hp.is_symlink() or cp.is_symlink():
        raise ValueError("symlinked source forbidden")
    h,c=apply(hp.read_text(),cp.read_text(),raw.decode("utf-8"))
    hp.write_text(h)
    cp.write_text(c)
    print("PUBLIC_MT6990_ETHERNET_STABLE618_SOURCE_REBASED_NOT_COMPILED")
    print("C_UNIT_ETHERNET_RUNTIME_NOT_PROVEN")


if __name__=="__main__":
    main()
