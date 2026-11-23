# 4号機 G4: eth1(MAC1) → SGMII1 → MT7531 CPU5 → LAN2経路修正（2026-11-23）

## ①共通ローダーの実機結果と最重要訂正

[4号機G4実機コメント](https://github.com/Karin-Laboratory/Debian13-Terminal6/pull/46#issuecomment-7094791584)によれば、署名済みP25全量SHA `2fc47ec23959faf7efee337e86bc2d3d777c7aca196614ed2b375a36e0214493` で **G1 Linux/内蔵rescue PASS・G2 UART PASS・G3 eMMC/GPT列挙部分PASS・G4 LAN2 FAIL**。Ethernet MAC `eth0` と `eth1` は登録されたものの、vendor `/gsw@0` (`mediatek,mt753x`) にドライバがbindせず、`lan2`のnetdevが生成されなかった。P26がext4条件に合わないためRAM rescueになったがP26/P44未変更。試験は純正Bへ復帰、C号機は保存基準機として一切操作なし。

**Linuxの`eth5`ではない**。過去のTest24および旧実験P25の実物DTBで確認した物理構成は次のとおり。

```
SoC MediaTek MT6990
  Ethernet MAC1 → Linux eth1
       │
       └── SGMII1（SoC digital PCS1 + analog PHY1）
                  │ 2.5GBASE-X CPU uplink（外部ジャックの速度とは別）
             MT7531 switch CPU port 5
                  │
             MT7531 switch user port 1
                  │
               Linux DSA lan2 → 外部RJ45
```

[過去Test24レポート](https://github.com/Karin-Laboratory/openwrt-terminal-6/blob/main/docs/NETSYS-SGMII1-BOOT-CANDIDATE.md)では**手動のPLL→PCS→Gen2アナログPHY初期化後、双方向IPv4通信PASS**。しかしこの成功は現行Linux 6.18.63のコールドブートやFDTに自動継承されない。

## 旧P25実物との比較により分かったこと

- [所有者非公開のSHA固定DTB比較CI #45144275431](https://github.com/Karin-Laboratory/SBAT6A-Offline-Archive/actions/runs/45144275431)：**SUCCESS**。以前`lan2`が登録されていた標準DSA P25 unsigned `d2ad2d7f…`と今回GSW版 unsigned `23080614…`は**kernel gzip / 内蔵initramfsが完全一致**。違いはFDTの構成。前者はMDIO addr 31の`mediatek,mt7531`、switch CPU `port@5 reg=<5>`の`ethernet` phandleが`mac@1`と一致し、user `port@1`が`lan2`であることを独立パーサで検証。
- 旧DSA P25は`eth1`、`lan2`と物理リンクを生成したが、ARP/ICMP 0応答で`lan2` TX / `eth1` TXが増えなかった。**単に旧DSA FDTへ戻すだけでは同じG4 FAILの再演**。
- 直近GSW版はNETSYS親に`simple-bus`とaddress/size cellを加えることでEthernet MAC `eth0`/`eth1`生成まで進んだ。つまりNETSYS側は修正の一部に成功。旧vendor`mediatek,mt753x`は新kernelの`mt7530-mmio` OF表にはなく、resource`reg`もないためbind不能。MMIO`reg`を推測したり、`compatible=mediatek,mt7988-switch`に偽装することは禁じる。

## アナログPHYとPLLについての重要な訂正

[PHY/PCS exact source audit CI #45144018543](https://github.com/Karin-Laboratory/SBAT6A-Offline-Archive/actions/runs/45144018543) **SUCCESS**。

従来の“アナログPHY・PLLノードが存在しない”は不正確。**物理アドレスの一致する旧vendor FDTノードは両方すでに存在**し、追加で同一MMIOを再定義してはならない。

- **PHY1**：`/sgmiiphy@11E60000` (`reg=0x11e60000, size=0x10000`)、phandle `0x70`、旧compatible `mediatek,colgin-sgmiisys_phy_1`。
- **PLL**：`/sgmiipll@10014000` (`reg=0x10014000, size=0x1000`)、phandle `0x73`、旧compatible `mediatek,colgin-sgmiisys_pll`。
- **digital SGMII1**：`/sgmiisys@11305000`、phandle `0x6e`、旧compatible `mediatek,colgin-sgmiisys_1`。
- **power-domain/SPM provider**：`/power-controller@12001000`、`mediatek,mt6990-scpsys`+`syscon`、phandle `0x23`。確定バインディングの`MT6990_POWER_DOMAIN_SGMII_TOP_1=21`。

Archived Linux `pcs-mtk-lynxi.c`は`mediatek,mt6990-sgmiisys`を検出した場合のみMT6990独自PCS経路を選び、`phys`経由でanalog `mt6990-sgmii-phy`を呼ぶ。前回vendor FDTには**その新compatibleと`phys` consumer配線がなかった**。PHYドライバは`mediatek,sgmii-pll`・`mediatek,spm`・`mediatek,sgmii-id=1`、単一`power-domains=<scpsys 21>`を要求する。

## もう一つのLinuxカーネル側リスク：共有SGMII_TOPの破壊的リセット

アーカイブの`drivers/phy/mediatek/phy-mtk-mt6990-sgmii.c` `mt6990_sgmii_phy_reset()`に **`mt6990_sgmii_top_cycle()` が存在し、共有電源ドメインをdown/upする**ことを確認した。FDTだけ有効化するとこの処理が実行される可能性がある。

[公開のGPL-source patch](https://github.com/Karin-Laboratory/openwrt-terminal-6/blob/main/patches/mt6990/0002-air6-avoid-sgmii-top-cycle.patch)はそのcycleを除き、共有PLL/PM frameworkを維持したままGen2再設定する。**PHY1を使う新FDTと、パッチ適用した新カーネルはセット**。古いカーネルに新FDTだけを組み合わせない。

## GitHub修正（実装と検証）

非公開作業ブランチ `Karin-Laboratory/SBAT6A-Offline-Archive:codex/c4-g4-cpu5-dsa-and-phy-contract-20261123`

- `tools/stage_c4_cpu5_sgmii1_fdt.py`: 旧vendor PHY1/PLL/PCS1実物ノードを再利用し、`power-domains=21`とPHY consumer配線、標準MDIO31 MT7531 CPU5/port1 LAN2を作成。bind不能なlegacy`/gsw@0`は無効化し、重複MMIOノードを作らない。NETSYS 2/2/simple-bus、他ノード・値は維持。
- `tools/verify_c4_cpu5_sgmii1_fdt.py`: 別実装によるsemantic FDT node/prop whitelist、正しいphandle、MAC1/CPU5/port1、PHY1/PLL/SCPSYSの実物アドレス保全を検証。
- [FDT stage CI #45145053702](https://github.com/Karin-Laboratory/SBAT6A-Offline-Archive/actions/runs/45145053702) **SUCCESS**、2回同一生成・独立検証PASS。**standalone DTB table SHA256 `0fe55616ea5894ece79f7b38f8b06804de4e22b52fcb54625c1b597518b06c0f`**。
- 完全なP25へは**レビュー済みの非破壊PHY resetパッチをLinuxソースへ適用してImageを再コンパイルする必要**がある。未署名P25は製造/検証CIの完了時だけSHAを確定する。

## 厳密な残ゲート

**DTB stage PASS ≠ コンパイル済みImage PASS ≠ LK G1 PASS ≠ Ethernet MAC/MDIO DSA bind ≠ 双方向TCP/ICMP PASS。** 特に新カーネルは旧G1〜G3起動成功のバイトを保持できず、実機への自動PASS継承は禁止。

同時に、P26がext4としてマウントできずRAM rescueとなる問題は**独立したG3条件**であり、ネットワーク修復と混同しない。4号機は最後に確認されたstock slot B、現在の`boot_a`には旧試験版が残る。C号機は完成済みDebian基準機として保管。**今回の作業はソース・非公開Actionsのみで、署名、実機接続、書込み、slot切替、再起動をしない**。
