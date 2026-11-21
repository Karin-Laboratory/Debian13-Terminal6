# 共通ローダーv1.0 C号機受入：LAN2 netdev欠落とFDT限定修正（2026-11-22）

## 1. 実機フィードバック：前候補 `c37400a6...`

- 2026-11-22にC号機へ投入した署名済みP25 SHA-256：`c37400a6788436773fb69b4fd4ed65193fd414df2e5d30d7514894f6cde00314`。32MiBのデバイス全量読戻しとraspi4独立読戻しのSHA・バイト比較 **PASS**。
- **G1** LK署名検証→FDT処理→Linux `6.18.63-debian-t6-proto2`→カーネル内蔵initramfs `/init`→UART管理シェル **PASS**。前候補のLK `mrdump_debug_kinfo_fdt_setup` ASSERTは今回再発しなかった。
- **G2** UART管理シェル操作 **PASS**。
- **G3** eMMC/GPT認識、P26 `rootfs_a` ext4を`/config`へマウント **PASS**。95MHz/CQE等のクロック・モード実測は **NOT_TESTED**。
- **G4** LAN2 **FAIL**。loaderが`TERMINAL6_LOADER_LAN2_UNAVAILABLE_UART_ONLY`を出力、`ip link`にEthernet MAC/DSA/lan2のnetdevが存在しない。link up/downやパケット転送以前の段階。
- **G5 SSH**、kexec/Debian第2段：先行LAN2未達により **NOT_TESTED**。
- 試験後、純正slot Bへ復帰し、当時のB `success=1`、ping、厳格なホスト鍵照合のSSH **PASS**。boot_b/LK/GPT/P44には書込みなし。Aのretry値が `03`→`04` に変化したが意味は未確定。後続のraspi4再接続はSSH認証拒否となり、最終確認以降の再測定は不可。
- 元証拠：[Draft PR #43、実機報告コメント](https://github.com/Karin-Laboratory/Debian13-Terminal6/pull/43#issuecomment-7068752653)。生UARTログ、個体固有データはraspi4の非公開領域のまま。

## 2. 署名済みP25と同じ内部構造のunsigned原本によるオフライン解析

非公開ActionsによるSHA固定入力の独立読取：
- [CI #44946842744](https://github.com/Karin-Laboratory/SBAT6A-Offline-Archive/actions/runs/44946842744) **SUCCESS**。
- 対象unsigned原本 SHA-256 `cc13517ca9c00b350eeb1c10fb15e4d1e1139993bb34332e441120ca9ed6a0a5`、ARM64 Image SHA-256 `f1cc341b3982e42df9c825e7da949f6fff99380268af9188389fb76b3e736d79`、既知成功DTBセクション SHA-256 `49fc129e2dd7ccc2d2ed4c0c4cac461e33566e2dda164f4ec06d5577baa4286a`。
- **ドライバ設定は既に有効**：`CONFIG_NET_MEDIATEK_SOC=y`、`CONFIG_NET_DSA=y`、`CONFIG_NET_DSA_MT7530=y`、`CONFIG_NET_DSA_MT7530_MDIO=y`、`CONFIG_PCS_MTK_LYNXI=y`、`CONFIG_PHY_MTK_MT6990_SGMII=y`。組込Imageに`mediatek,mt6990-eth`と`mediatek,mt7531`の文字列が存在する。
- 元FDTは`/netsys@15100000`を`mediatek,mt6990-netsys`とのみ宣言し、**`simple-bus`互換がなく、`#address-cells`と`#size-cells`もない**。ただし空の`ranges`はある。配下`/netsys@15100000/ethernet@15100000`は`mediatek,mt6990-eth`、`status=okay`だが、自動的なOF子ノード展開とMMIOアドレス変換は期待できない。
- 従来switchはルートの`/gsw@0`、`compatible=mediatek,mt753x`、`port@5`はSGMII。**`mediatek,mt753x`は組込Imageの文字列に存在しない**一方、標準DSAの`mediatek,mt7531`は存在する。
- この組合せは[OpenWrt側で記録したTest22～Test24のNETSYS/SGMII1解析](https://github.com/Karin-Laboratory/openwrt-terminal-6/blob/main/docs/NETSYS-SGMII1-BOOT-CANDIDATE.md)と整合する。**OF parentがバス化されていないことが有力な根本要因**。ただし今回のUART生ログからprobeエラーの正確なreturn codeまで再確認できていないため、直接原因の断定・実機修正済み判定は禁止する。

## 3. 新しい署名前候補：ブート成功Linuxを一切変更しないDTB限定修正

公開NETSYS調査の構造を参照した、[非公開Draft PR #191](https://github.com/Karin-Laboratory/SBAT6A-Offline-Archive/pull/191) にsource-onlyビルダーと別実装の独立検証器を保存。

- 既にG1–G3で実機PASSしたARM64カーネルgzip、内蔵loader initramfs、cmdline、boot-v2外部ramdisk `size=0`、既存のP25アドレス配置は**一切変更しない**。
- 元FDTのNETSYS親へ`compatible = "mediatek,mt6990-netsys", "simple-bus"`、`#address-cells=<2>`、`#size-cells=<2>`を追加し、既存の空`ranges`（identity変換）を維持。
- 既存Ethernet `mdio-bus`の下に`switch@1f`を追加：`mediatek,mt7531`、MDIO addr 31、port1=`lan2`、CPU port5、MAC1へのphandle、2500base-x fixed-link。既存`/gsw@0`など純正FDTの既存ノードとプロパティは保持。
- 新FDTの追加パス・許可プロパティ以外の変更は禁止し、独立FDTパーサでノード/プロパティ同一性、MDIO31、CPU5→MAC1、port1 label、boot headerと署名ゼロ末尾、SHA1 boot IDを検査。
- **新unsigned P25 SHA-256：`5a73830e708263584973b890433291a1886bd4ec4808c3196d2a088ffa0c6e80`**、33,554,432 bytes。後続の署名済みSHAはまだ存在しない。
- [非公開Actions製造CI #44947195725](https://github.com/Karin-Laboratory/SBAT6A-Offline-Archive/actions/runs/44947195725) **SUCCESS**：源SHA照合、2回独立P25組立のbyte比較、producer-independent検証、SHA256SUMS、Draft Releaseからの3資産再取得・cmp／SHA照合PASS。
- **非公開Draft Release ID `453967284`**、tag `cunit-v10-lan2-dtb-only-unsigned-44947195725`。unsigned P25 asset ID `776806257`、BUILD-RECEIPT asset ID `776806498`、SHA256SUMS asset ID `776806565`。署名秘密鍵や生UARTログを含まず、非公開を維持。

## 4. 未達事項・次の受入ゲート

**この候補は `UNSIGNED_PRESIGN_MANUFACTURE_AND_READBACK_PASS`。実機でのLinux起動、LAN2、SSH、kexecをPASSとしない。**

次回C号機実機試験では、FDTだけが異なってもLKの起動経路が変わり得るため、**最初にG1（LK/FDT/Linux/内蔵loader）を回帰確認**。続いてG2 UART、G3 MMC/P26を再測定し、G4では`platform device`生成→MAC netdev→MDIO/MT7531 DSA→lan2 PHY link→ARP/TCPの順に検証する。実機の初期化でClock/PCS/PHY/PM/DMAが失敗する可能性は残る。G4をPASSしなければG5 SSHと第2段kexecへ進まない。

**前回FAIL署名済み `d259237b...`、原因修正前の `c37400a6...` を次回の新候補として再利用しない。** 個別のSHAを指定した所有者承認なしに新しいP25の署名・C号機書込み・slot切替・再起動はしない。純正slot BやP26/P43/P44/GPT/LKへの変更は行っていない。

C号機は①②交互実機試験の暫定方針に従い、次の実機試験に対して排他・手動復旧経路を維持する。
