# 4号機 ①共通ローダー CPU5/PHY1 署名済みP25：確定記録（2026-11-23）

## 正本ハッシュ

所有者承認済み unsigned SHA256:
4977a6bb94ad7dd15a82d09355a16e3417e9a560fa596a42a18cd88c98c68aa3

**署名済み P25 SHA256:
e65edfd6bfce77e8af9b161afa4618a0f8e04cff28597f8e83ddc29b5e1ee237**

- 署名済みサイズ：33,554,432 bytes (32 MiB)
- ファイル名：C4-CPU5-PHY1-4977a6bb-SIGNED-UNTESTED-p25.img
- 非公開Draft Release ID：**455513829**
- 署名済みP25 asset ID：**783192364**
- 独立暗号検証レシート asset ID：**783192722**、1818B、SHA256 e9f899737eb52a2b08f2dc4686b41153a374353338f7a5057b73129bbe677484
- [署名GitHub Actions #45190759621](https://github.com/Karin-Laboratory/SBAT6A-Offline-Archive/actions/runs/45190759621)：preflight／sign-once とも **SUCCESS**。
- [非公開Draft PR #203](https://github.com/Karin-Laboratory/SBAT6A-Offline-Archive/pull/203)。
- 完成した署名ジョブのGit commit：5a2343743e20d9d8804308373a74fac0501a75ec。
- Release assetをIDで再取得、署名済み32MiBとレシートの全量cmp／SHA256が一致。GitHub Release RESTでもDraft、size、digestを再確認してPASS。

## ソース構成と署名時の検証

- Linux 6.18.63-debian-t6-proto2を、SGMII_TOP共有電源の破壊的cycleを避けるPHYリセットパッチを適用して**再コンパイル**。新ARM64 Image SHA256 e9953eaded3ce1bfb7275af0f087843b3d4c10f82c6b73827c1cc88cc1179723。
- 内蔵レスキューCPIO SHA256 ff14bbfbb2ab376b95235a0ed9e57db8bc6435147c49492a654ada9aa459aa9a は既知起動版と同一、Android boot-v2外部ramdiskは0。
- 正しい配線：Linux eth1 (SoC MAC1) → SGMII1/PCS1/PHY1 → MT7531 switch **CPU port5** → switch user port1 (DSA lan2)。Linux eth5ではない。
- 新FDT table SHA256 0fe55616ea5894ece79f7b38f8b06804de4e22b52fcb54625c1b597518b06c0f。旧vendor GSWはdisabled、MDIO31 MT7531 DSA。既存PHY1・PLLノードを再利用し、重複MMIO定義はない。
- [製造CI #45145678051](https://github.com/Karin-Laboratory/SBAT6A-Offline-Archive/actions/runs/45145678051)：未署名32MiB 2回byte一致、独立boot-v2/FDT/Kconfig検証、private Release全7資産の再取得byte一致がPASS。
- 署名時に新Image・新DTB・Kconfig・前版P25・内蔵CPIOをasset IDとSHAで固定。保護self-hosted runner、既知成功した署名ツール固定コミット、exclusive LOCKと一度限りのSHA専用MARKERを使用。別プロセスでROOT／IMAGE証明書の独立RSA-PSS検証、署名前後のboot body一致、署名済み32MiB全量SHA、private Release再取得PASS。

## 実機との厳密な境界

**最終判定：EXACT_SHA_RSA_PSS_SIGNED_AND_PRIVATE_READBACK_PASS。**

- **新カーネルの G1 LK/Linux、G2 UART、G3 eMMC/P26、G4 LAN2/ARP/ICMP、G5 SSH/kexecはすべてNOT_TESTED。** 旧ビルドG1–G3の起動成功を新Imageに継承しない。
- P26がext4として利用できずRAM rescueとなる問題は独立したG3課題。
- 今回4号機・C号機への接続／書込み／bootctl／起動slot変更／再起動なし。4号機は前回最終確認時点でstock slot B、C号機はDebian 13基準機として保存。
- 次の4号機試験には別途所有者の実機操作承認が必要。署名済み完全SHAを固定した単発G1→G2→G3→G4→G5の受入試験とし、最初のFAILで停止・純正B復帰。LAN2のlinkやnetdevができただけで通信成功とみなさない。
