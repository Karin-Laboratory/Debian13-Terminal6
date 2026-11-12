#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Reviewed, exact-input-hash resolutions for the retained MT6990 stable port.

Missing old Realtek/selftest paths remain deleted: the retained OpenWrt source
omits them; they are outside the C-unit management path. MT6990 identifiers and PCS list support remain;
upstream EEE, read-error handling, RCU barrier and early dummy allocation remain.
"""
import hashlib
import re
pattern=re.compile(r'(?ms)^<<<<<<< [^\n]*\n(.*?)^\|\|\|\|\|\|\| [^\n]*\n(.*?)^=======\n(.*?)^>>>>>>> [^\n]*\n')
def resolve_content(name, merged, stable):
    if name=='tools/scripts/Makefile.include':
        result=stable
        anchor='CC_NO_CLANG := $(shell $(CC) -dM -E -x c /dev/null | grep -Fq "__clang__"; echo $$?)\n'
        assert result.count(anchor)==1
        return result.replace(anchor,anchor+'HOSTCC_NO_CLANG := $(shell $(HOSTCC) -dM -E -x c /dev/null | grep -Fq "__clang__"; echo $$?)\n')
    index=0
    def choose(m):
        nonlocal index
        index+=1
        board,base,new=m.groups()
        if name=='net/netfilter/nf_flow_table_core.c': return board+new
        if name=='drivers/net/phy/phylink.c': return '\tif (!pcs_found || IS_ERR_OR_NULL(pcs))\n'
        if name=='drivers/net/pcs/pcs-mtk-lynxi.c': return board
        if name=='drivers/net/ethernet/mediatek/mtk_eth_soc.h':
            if index in (1,2): return board+new
            assert index==3
            return board.replace('MTK_SRAM)', 'MTK_SRAM | MTK_GMAC_EEE)')
        if name=='drivers/net/ethernet/mediatek/mtk_eth_soc.c':
            if index==1: return board
            if index==2:
                # Keep board's delayed phylink_create, but retain stable EEE setup.
                return new[:new.index('\tphylink = phylink_create')]
            assert index==3
            return ''  # Stable moved dummy allocation before register_netdev.
        raise ValueError(name)
    result=pattern.sub(choose,merged)
    if name=='drivers/net/pcs/pcs-mtk-lynxi.c':
        anchor='\tregmap_read(mpcs->regmap, SGMSYS_PCS_CONTROL_1, &bm);\n\tregmap_read(mpcs->regmap, SGMSYS_PCS_ADVERTISE, &adv);'
        assert result.count(anchor)==1
        result=result.replace(anchor,'\tif (regmap_read(mpcs->regmap, SGMSYS_PCS_CONTROL_1, &bm) ||\n\t    regmap_read(mpcs->regmap, SGMSYS_PCS_ADVERTISE, &adv)) {\n\t\tstate->link = false;\n\t\treturn;\n\t}')
    if name=='drivers/net/ethernet/mediatek/mtk_eth_soc.c':
        anchor='phy_mode, &mtk_phylink_ops);'
        assert result.count(anchor)==1
        result=result.replace(anchor,'phy_mode, mac_ops);')
        anchor='\tnetif_napi_add(eth->dummy_dev, &eth->tx_napi, mtk_napi_tx);'
        assert result.count(anchor)==1
        result=result.replace(anchor,'\teth->dummy_dev->threaded = 1;\n\tstrcpy(eth->dummy_dev->name, "mtk_eth");\n'+anchor)
        assert result.count('eth->dummy_dev = alloc_netdev_dummy(0);')==1
    assert '<<<<<<<' not in result
    return result

REVIEWED={'net/netfilter/nf_flow_table_core.c': {'base': 'ba593870bfcf6650c508e56e623b6e9654b69d3af327ac48be2fd1f4498b3f09', 'board': '39d393383fa478defe1ddc0612d2b45014b7c88fc4c32614bd2e56ca207e8066', 'stable': '5f15cbf95b7b1c49463397f4ac84cd3e5ac6edbcddb154bc742e26311100115b', 'resolved': 'e1054e20214c38534d7c8a38009327b10cdcf4db927641867ce08950623463bd'}, 'tools/scripts/Makefile.include': {'base': '5791a2a0a175ad9d0f30348d9a6de32ad5473cadd6f3edd3b832484104462915', 'board': '5abdbf7b37a9b165f447bac1eed24e64b04c346562d0f798800560fe71ec4829', 'stable': '8816ea7922081e082af9a67dd6c21ee6eef767e838c3cd100dda57e4c116e537', 'resolved': 'ca38fbc789b2867612e0d83f252b711b05d1148656f591e0af2f43b8de60cb0e'}, 'tools/testing/selftests/ftrace/test.d/kprobe/kprobe_non_uniq_symbol.tc': {'base': '29e97852b8f0977716ec60317fdba339da24c0505ba3d793c727fed09f9b39f6', 'board': None, 'stable': 'b29bf7ed7900c1e5d3b3e400f4fd915b59a58eeafea3b265d7d0a4d9588f3469', 'resolved': None}, 'tools/testing/selftests/ftrace/test.d/dynevent/add_remove_uprobe.tc': {'base': '7e8e856aa4e4a14e99c4023cb15bf770a15b2364bdea9534c678a7b28a9ca30e', 'board': None, 'stable': '2a1f5f5b367ce866cbe8cc1947b5fbaa79fd4290fc21e323264ec9fcc435d296', 'resolved': None}, 'tools/testing/selftests/ftrace/test.d/dynevent/add_remove_eprobe.tc': {'base': '95fb6051da246860f83e63d69c6ccc4e3fce126bd256e7cb858d43abcea77caa', 'board': None, 'stable': '74471b0c1ccc037382c12b317f032669901fded64d66fc4f99e0f6544fd84a8a', 'resolved': None}, 'drivers/net/phy/phylink.c': {'base': '440db1a9c997855722f5cdd18a384668fff421ffa3b341f4ac78a24173af77e1', 'board': '907b88e78a95d9f0000f66c83cc6e3235a0235b90c6e9021d7b8da14834b7e7d', 'stable': '4affee8b3330cdba2c9d563aa16dbab4997898a2ef03e38ec010aaeda780ef82', 'resolved': '03c9ee86d06d28badeef304931be62a05de3326224ded8553540ebf52ceade81'}, 'drivers/net/pcs/pcs-mtk-lynxi.c': {'base': 'afa34e0ce2c37a97ada36a83fd1d43fdfeb70ffb3e1d99208ea3785b0587c45f', 'board': 'c3b8bb1e1ae48c038e7e128acc7af2b52f42bf4bc024164cf34d444a2c080f31', 'stable': '5ac02f1c7c0710c843a21491fa1b5f713446c1e17d2a4daaffe974c0695ce2d1', 'resolved': '1773da4890791602b878ca8a374a46adfbda50aed5c4132fc39ebc900e361f19'}, 'drivers/net/dsa/realtek/rtl8365mb.c': {'base': '5cc9a25d8277f72daa56a66d8c12c2c484fc3055cde99bb445b0416d1eb61fe9', 'board': None, 'stable': '75f4bade45ea568d45d66e4bc19f0cd8d8d7a095c8892e74c69dc79ac8e7d86b', 'resolved': None}, 'drivers/net/ethernet/mediatek/mtk_eth_soc.c': {'base': 'f32d0e3de3649243ee6307ac0a1a07bfcd40d564d1f10329dcd6cd01d4ecb06d', 'board': 'b9f948b4585dca74be3192136acd672ad35f36d24a5798e56c8c88687c52e195', 'stable': 'af2d5ac1754d8b3deb009f13100b07cee983d5cf74e6192f2952971378c1138b', 'resolved': '59c8468c5ed57e8335a08f337cb85b0d58334423d88c8b8aa358d8f6893483d2'}, 'drivers/net/ethernet/mediatek/mtk_eth_soc.h': {'base': '7eb2d4a31d2af8b3f92db32d486aa9c5882f00d9b357bd4523552237a3da76bd', 'board': 'd747890f87435ae3e0e211424404fa713612686a8e8bf00c1cbb1a3c63a1d4b9', 'stable': '0383f85acb12df3dbdcd13c6e1c41095b7d9e318c4a9cb038d57bdff9f01f93c', 'resolved': '8963c0f0a67a385bc2d538cb488848645aa17932ccdde73f11c91aaad42d8ae2'}}

def resolve(name, base, board, stable, merged):
    spec=REVIEWED.get(name)
    if spec is None: return False, None
    def sha(data): return hashlib.sha256(data).hexdigest() if data is not None else None
    for key,data in (("base",base),("board",board),("stable",stable)):
        if sha(data)!=spec[key]: return False, None
    result=None if board is None else resolve_content(name,merged.decode(),stable.decode()).encode()
    if sha(result)!=spec["resolved"]: raise ValueError("resolution output digest mismatch: "+name)
    return True,result
