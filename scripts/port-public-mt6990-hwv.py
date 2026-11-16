#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Port a pinned public HWV-only mux patch to Linux v6.18.63 without FENC guesses."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path

PATCH="patches/0956-clk-mediatek-add-real-hwv-only-mux-ops.patch"
HEADER="drivers/clk/mediatek/clk-mux.h"
SOURCE="drivers/clk/mediatek/clk-mux.c"
COUNTS=[[1],[34],[28],[2],[11]]


def blocks(patch):
    hunk=None
    hunks=[]
    file=None
    for line in patch.splitlines():
        if line.startswith("+++ b/"):
            file=line[6:]
        if line.startswith("@@ "):
            hunk={"file":file,"groups":[],"open":[]}
            hunks.append(hunk)
            continue
        if not hunk:
            continue
        if line.startswith("+") and not line.startswith("+++ "):
            hunk["open"].append(line[1:])
        elif hunk["open"]:
            hunk["groups"].append(hunk["open"])
            hunk["open"]=[]
    if hunk and hunk["open"]:
        hunk["groups"].append(hunk["open"])
    if ([list(map(len,h["groups"])) for h in hunks]!=COUNTS or
        any(h["file"]!=(HEADER if i<2 else SOURCE) for i,h in enumerate(hunks))):
        raise ValueError("unexpected public HWV patch structure")
    return ["\n".join(h["groups"][0])+"\n" for h in hunks]


def replace_once(s,needle,replacement):
    if s.count(needle)!=1:
        raise ValueError("stable Linux HWV anchor absent or ambiguous: "+needle[:80])
    return s.replace(needle,replacement)


def port(header,source,patch):
    p=blocks(patch)
    if "mtk_mux_gate_hwv_clr_set_upd_ops" in header or "static int mtk_clk_mux_hwv_enable(" in source:
        raise ValueError("HWV-only mux code already present")
    needle="extern const struct clk_ops mtk_mux_gate_hwv_fenc_clr_set_upd_ops;\n"
    header=replace_once(header,needle,needle+p[0])
    needle="#define MUX_GATE_HWV_FENC_CLR_SET_UPD_FLAGS("
    header=replace_once(header,needle,p[1]+needle)
    needle="static int mtk_clk_mux_hwv_fenc_enable("
    source=replace_once(source,needle,p[2]+needle)
    old="\tif (ops == &mtk_mux_gate_hwv_fenc_clr_set_upd_ops)\n"
    source=replace_once(source,old,p[3])
    needle="const struct clk_ops mtk_mux_gate_hwv_fenc_clr_set_upd_ops = {"
    source=replace_once(source,needle,p[4]+needle)
    if source.count("mtk_mux_gate_hwv_clr_set_upd_ops")<3 or header.count("MUX_GATE_HWV_CLR_SET_UPD")<2:
        raise ValueError("incomplete HWV stable source rebase")
    return header,source


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--stage",required=True,type=Path)
    ap.add_argument("--linux",required=True,type=Path)
    a=ap.parse_args()
    receipt=json.loads((a.stage/"source-receipt.json").read_text())
    ents=[x for x in receipt.get("files",[]) if x["destination"]==PATCH]
    if len(ents)!=1:
        raise ValueError("HWV donor receipt missing")
    patch_file=a.stage/PATCH
    raw=patch_file.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=ents[0]["sha256"]:
        raise ValueError("pinned public HWV patch digest mismatch")
    hp=a.linux/HEADER
    cp=a.linux/SOURCE
    if hp.is_symlink() or cp.is_symlink() or not hp.is_file() or not cp.is_file():
        raise ValueError("non-regular CLK files")
    h,c=port(hp.read_text(),cp.read_text(),raw.decode("utf-8"))
    hp.write_text(h)
    cp.write_text(c)
    print("PUBLIC_MTK_HWV_ONLY_STABLE618_SOURCE_REBASED_NOT_COMPILED")


if __name__=="__main__":
    main()
