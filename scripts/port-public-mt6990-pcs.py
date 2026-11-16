#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Rebase the SHA-pinned GPL MT6990 PCS sequence to the stable 6.18 PCS API.

The original donor 974 patch targets an OpenWrt-modified PCS platform driver.
Upstream stable 6.18 has mtk_pcs_lynxi_create(dev, regmap, offset, flags)
instead. Preserve the donor's MT6990 force-2.5G register ordering but use
the supported stable API. This is not a hardware-validated SGMII driver.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path

PATCH="patches/974-net-pcs-mtk-lynxi-add-mt6990-variant.patch"
PCS="drivers/net/pcs/pcs-mtk-lynxi.c"
HEADER="include/linux/pcs/pcs-mtk-lynxi.h"
ETH="drivers/net/ethernet/mediatek/mtk_eth_soc.c"


def replace_one(s, before, after):
    if s.count(before)!=1:
        raise ValueError("stable source anchor missing/ambiguous: "+before[:90])
    return s.replace(before,after)


def port(pcs,header,eth,donor):
    for token in ("MT6990_SGMSYS_RESERVED_VAL", "0x001000fa",
                  "0x31120009", "mtk_pcs_mt6990_config"):
        if token not in donor:
            raise ValueError("upstream MT6990 PCS sequence changed: "+token)
    if "MTK_SGMII_FLAG_MT6990" in header or "mtk_pcs_mt6990_config" in pcs:
        raise ValueError("MT6990 PCS path already installed")
    header=replace_one(header,
        "#define MTK_SGMII_FLAG_PN_SWAP BIT(0)\n",
        "#define MTK_SGMII_FLAG_PN_SWAP BIT(0)\n"
        "#define MTK_SGMII_FLAG_MT6990 BIT(3)\n")
    pcs=replace_one(pcs,
        "#define SGMII_DEV_VERSION\t\tGENMASK(31, 16)\n",
        "#define SGMII_DEV_VERSION\t\tGENMASK(31, 16)\n"
        "\n#define MT6990_SGMSYS_RESERVED\t\t0x24\n"
        "#define MT6990_SGMSYS_RESERVED_VAL\t0x001000fa\n")
    vendor_config = (
        "static int mtk_pcs_mt6990_config(struct mtk_pcs_lynxi *mpcs,\n"
        "\t\t\t\tphy_interface_t interface)\n"
        "{\n"
        "\tbool changed = mpcs->interface != interface;\n"
        "\tu32 check;\n"
        "\tint ret;\n"
        "\n"
        "\t/* SDK's MT6990 Gen2 fixed 2.5G path, not generic LynxI AN. */\n"
        "\tif (interface != PHY_INTERFACE_MODE_2500BASEX)\n"
        "\t\treturn -EINVAL;\n"
        "\tret = regmap_update_bits(mpcs->regmap, mpcs->ana_rgc3,\n"
        "\t\t\t\t SGMII_PHY_SPEED_MASK, SGMII_PHY_SPEED_3_125G);\n"
        "\tif (ret)\n\t\treturn ret;\n"
        "\tret = regmap_clear_bits(mpcs->regmap, SGMSYS_PCS_CONTROL_1,\n"
        "\t\t\t\t BMCR_ANENABLE);\n"
        "\tif (ret)\n\t\treturn ret;\n"
        "\tret = regmap_write(mpcs->regmap, SGMSYS_SGMII_MODE,\n"
        "\t\t\t\t 0x31120009);\n"
        "\tif (ret)\n\t\treturn ret;\n"
        "\tret = regmap_clear_bits(mpcs->regmap, SGMSYS_QPHY_PWR_STATE_CTRL,\n"
        "\t\t\t\t    SGMII_PHYA_PWD);\n"
        "\tif (ret)\n\t\treturn ret;\n"
        "\tret = regmap_write(mpcs->regmap, MT6990_SGMSYS_RESERVED,\n"
        "\t\t\t\t MT6990_SGMSYS_RESERVED_VAL);\n"
        "\tif (ret)\n\t\treturn ret;\n"
        "\tret = regmap_read(mpcs->regmap, MT6990_SGMSYS_RESERVED, &check);\n"
        "\tif (ret || check != MT6990_SGMSYS_RESERVED_VAL)\n"
        "\t\treturn -EIO;\n"
        "\tret = regmap_clear_bits(mpcs->regmap, SGMSYS_QPHY_PWR_STATE_CTRL,\n"
        "\t\t\t\t    SGMII_PHYA_PWD);\n"
        "\tif (ret)\n\t\treturn ret;\n"
        "\tmpcs->interface = interface;\n"
        "\treturn changed;\n"
        "}\n\n"
    )
    pcs=replace_one(pcs,"static int mtk_pcs_lynxi_config(",
                    vendor_config+"static int mtk_pcs_lynxi_config(")
    original="\tadvertise = phylink_mii_c22_pcs_encode_advertisement(interface,\n"
    pcs=replace_one(pcs,original,
        "\tif (mpcs->flags & MTK_SGMII_FLAG_MT6990)\n"
        "\t\treturn mtk_pcs_mt6990_config(mpcs, interface);\n\n"+original)
    original="\tif (neg_mode != PHYLINK_PCS_NEG_INBAND_ENABLED) {\n"
    pcs=replace_one(pcs,original,
        "\t/* Keep the SDK MT6990 SGMII_MODE after fixed-link config. */\n"
        "\tif (mpcs->flags & MTK_SGMII_FLAG_MT6990)\n"
        "\t\treturn;\n\n"+original)
    pcs=replace_one(pcs,
        "\tif (id != SGMII_LYNXI_DEV_ID) {\n",
        "\tif (!(flags & MTK_SGMII_FLAG_MT6990) &&\n"
        "\t    id != SGMII_LYNXI_DEV_ID) {\n")
    pcs=replace_one(pcs,
        "\tif (ver != 0x1) {\n",
        "\tif (!(flags & MTK_SGMII_FLAG_MT6990) && ver != 0x1) {\n")
    pcs=replace_one(pcs,
        "\tmpcs = kzalloc(sizeof(*mpcs), GFP_KERNEL);\n",
        "\t/* MT6990 lacks classic LynxI ID/version; reserved register must\n"
        "\t * still round-trip, to reject missing/clock-gated PCS.\n"
        "\t */\n"
        "\tif (flags & MTK_SGMII_FLAG_MT6990) {\n"
        "\t\tret = regmap_write(regmap, MT6990_SGMSYS_RESERVED,\n"
        "\t\t\t\t   MT6990_SGMSYS_RESERVED_VAL);\n"
        "\t\tif (ret)\n\t\t\treturn NULL;\n"
        "\t\tret = regmap_read(regmap, MT6990_SGMSYS_RESERVED, &id);\n"
        "\t\tif (ret || id != MT6990_SGMSYS_RESERVED_VAL)\n"
        "\t\t\treturn NULL;\n"
        "\t}\n\n"
        "\tmpcs = kzalloc(sizeof(*mpcs), GFP_KERNEL);\n")
    eth=replace_one(eth,
        '\t\tif (of_property_read_bool(np, "mediatek,pnswap"))\n'
        '\t\t\tflags |= MTK_SGMII_FLAG_PN_SWAP;\n',
        '\t\tif (of_property_read_bool(np, "mediatek,pnswap"))\n'
        '\t\t\tflags |= MTK_SGMII_FLAG_PN_SWAP;\n'
        '\t\tif (MTK_HAS_CAPS(eth->soc->caps, MTK_SOC_MT6990) &&\n'
        '\t\t    of_device_is_compatible(np, "mediatek,mt6990-sgmiisys"))\n'
        '\t\t\tflags |= MTK_SGMII_FLAG_MT6990;\n')
    eth=replace_one(eth,
        "\tif (MTK_HAS_CAPS(eth->soc->caps, MTK_SGMII)) {\n",
        "\tif (MTK_HAS_CAPS(eth->soc->caps, MTK_SGMII) &&\n"
        "\t    !MTK_HAS_CAPS(eth->soc->caps, MTK_SOC_MT6990)) {\n")
    eth=replace_one(eth,
        "\terr = mtk_hw_init(eth, false);\n"
        "\tif (err)\n"
        "\t\tgoto err_wed_exit;\n",
        "\terr = mtk_hw_init(eth, false);\n"
        "\tif (err)\n"
        "\t\tgoto err_wed_exit;\n"
        "\t/* MT6990 SGMIISYS may be power-gated until hardware clock init. */\n"
        "\tif (MTK_HAS_CAPS(eth->soc->caps, MTK_SOC_MT6990)) {\n"
        "\t\terr = mtk_sgmii_init(eth);\n"
        "\t\tif (err)\n"
        "\t\t\tgoto err_deinit_hw;\n"
        "\t}\n")
    return pcs,header,eth


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--source-stage",required=True,type=Path)
    ap.add_argument("--kernel-tree",required=True,type=Path)
    a=ap.parse_args()
    stage=a.source_stage
    receipt=json.loads((stage/"source-receipt.json").read_text())
    records=[x for x in receipt.get("files",[]) if x["destination"]==PATCH]
    if len(records)!=1:
        raise ValueError("pinned public MT6990 PCS source missing")
    blob=(stage/PATCH).read_bytes()
    if hashlib.sha256(blob).hexdigest()!=records[0]["sha256"]:
        raise ValueError("public MT6990 PCS SHA mismatch")
    paths=[a.kernel_tree/x for x in (PCS,HEADER,ETH)]
    if any(not x.is_file() or x.is_symlink() for x in paths):
        raise ValueError("stable Linux PCS paths invalid")
    code=port(*(x.read_text() for x in paths),blob.decode("utf-8"))
    for path,src in zip(paths,code):
        path.write_text(src)
    print("PUBLIC_MT6990_PCS_STABLE_6_18_REBASE_PASS_NOT_HW_VALIDATED")


if __name__=="__main__":
    main()
