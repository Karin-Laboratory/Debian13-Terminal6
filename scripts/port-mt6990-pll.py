#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Adapt the retained MT6990 PLL provider to the stable struct-device API."""
from pathlib import Path
import re
import sys

root = Path(sys.argv[1])
header = (root/'drivers/clk/mediatek/clk-pll.h').read_text()
if not re.search(r'int mtk_clk_register_plls\(struct device \*dev,', header):
    raise SystemExit('unexpected PLL registration API')
p = root/'drivers/clk/mediatek/clk-mt6990.c'
s = p.read_text()
old = 'mtk_clk_register_plls(node, plls, ARRAY_SIZE(plls),\n\t\t\tclk_data);'
new = '''r = mtk_clk_register_plls(&pdev->dev, plls, ARRAY_SIZE(plls),
                                  clk_data);
	if (r) {
		mtk_free_clk_data(clk_data);
		return r;
	}'''
if old in s:
    if s.count(old) != 1 or 'clk_mt6990_apmixed_probe(struct platform_device *pdev)' not in s:
        raise SystemExit('unexpected retained MT6990 PLL source')
    s = s.replace(old, new)
    p.write_text(s)
elif new not in s:
    raise SystemExit('MT6990 PLL source does not match reviewed port')
print('MT6990_PLL_DEVICE_API_PORT_PASS')
