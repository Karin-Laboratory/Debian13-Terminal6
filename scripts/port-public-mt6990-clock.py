#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Narrow stable-6.18 MT6990 top-clock source adaptation, fail closed.

The public MT6990 donor's obsolete clkdbg.h is only used by LDVT commands,
and stable PLL registration accepts device rather than device_node.
Do not substitute clock/PLL register layouts or disable safety checks.
"""
from pathlib import Path
import re
import sys

def port(path: Path):
    if not path.is_file() or path.is_symlink():
        raise ValueError("MT6990 clock source not a regular file")
    src=path.read_text(encoding="utf-8")
    header='#include "clkdbg.h"\n'
    if src.count(header)!=1 or re.search(r"\bclkdbg_(?!h\b)|\bclkdbg\b",src.replace(header,'')):
        raise ValueError("unexpected vendor clock debug dependency")
    old="mtk_clk_register_plls(node, plls, ARRAY_SIZE(plls),\n\t\t\tclk_data);"
    if src.count(old)!=1:
        raise ValueError("upstream PLL callsite changed")
    if src.count("static int clk_mt6990_apmixed_probe(struct platform_device *pdev)")!=1:
        raise ValueError("PLL probe is not the expected platform-device callback")
    replacement=(
        "r = mtk_clk_register_plls(&pdev->dev, plls, ARRAY_SIZE(plls),\n"
        "\t\t\tclk_data);\n"
        "\tif (r) {\n"
        "\t\tmtk_free_clk_data(clk_data);\n"
        "\t\treturn r;\n"
        "\t}"
    )
    # Donor bringup-only LDVT requires undefined cmd_fn and set_custom_cmds.
    # It can forcibly power down active PLLs and is not a Debian prerequisite.
    start = "/* for suspend LDVT only */"
    end = "static const struct of_device_id of_match_clk_mt6990[] = {"
    if src.count(start)!=1 or src.count(end)!=1:
        raise ValueError("expected donor LDVT block missing")
    pre, tail = src.split(start, 1)
    unwanted, post = tail.split(end, 1)
    if (unwanted.count("static const struct cmd_fn cmds[]")!=1
            or unwanted.count("CMDFN(")!=5
            or "pll_force_off(" not in unwanted
            or "subsys_force_off(" not in unwanted):
        raise ValueError("donor LDVT block changed shape")
    src = pre + end + post
    callback = "#ifdef CONFIG_MTK_CLK_CHECK\\n\\tset_custom_cmds(cmds);\\n#endif\\n"
    if src.count(callback)!=1:
        raise ValueError("LDVT-only probe hook missing")
    src = src.replace(callback, "")
    out=src.replace(header,'').replace(old,replacement)
    if out==src or 'mtk_clk_register_plls(node,' in out:
        raise ValueError("MT6990 clock stable API conversion not applied")
    path.write_text(out, encoding="utf-8")
    return {"status":"PUBLIC_MT6990_PLL_API_ADAPTED_UNCOMPILED", "removed_debug_include": True,
            "stable_PLL_device_api": True, "changed_lines": True}

if __name__=="__main__":
    if len(sys.argv)!=2:
        sys.exit("usage: port-public-mt6990-clock.py /absolute/kernel/clk-mt6990.c")
    p=Path(sys.argv[1])
    if not p.is_absolute():
        sys.exit("absolute path required")
    print(port(p))
