# 共通ローダーv1.0：起動成功Image固定・外部ramdisk方式の署名前候補（2026-11-21）

> 状態：**未署名P25 32MiB の実製造・静的独立検証PASS、非公開Draft Release再取得PASS（初回CI）**。**実機起動・LKの外部ramdiskロード・署名・OS切替は未達**。これは署名許可でも実機適用許可でもなく、従来tinyconfig候補を合格へ変更するものではない。

## 方針変更の根拠

[今回の失敗実測](CUNIT-LOADER-V10-G1-WDT-FAIL-20261121.ja.md)では、署名された `f112d3ea...` 由来P25がLKの署名受理後、Linux banner前にwatchdogになった。実物IKCONFIG比較は4776対2054設定キー、差3546。既知成功と失敗ImageはAndroid boot v2主要メモリ配置とDTBセクションが一致したがカーネル本体が異なった。

まず非公開アーカイブに保存されたKVM系のソース・ビルド保存物を読み戻し確認した。[非公開資産棚卸CI #44898451507](https://github.com/Karin-Laboratory/SBAT6A-Offline-Archive/actions/runs/44898451507) はPASSしたが、保存ビルドImage SHA `dd077159...` は11月21日C号機で実際に起動したImage SHA `141b6750...` と**一致しない**。ソース保存の存在を成功版の厳密再ビルド再現性と混同しない。

次の候補では**成功版そのもののgzipカーネルバイト列を再利用し、カーネルの再コンパイルを一切しない**。同一署名済み原本から取り出したDTBテーブルも保持。ローダーの変更は、Android boot v2独立ramdiskセクションへowner-privateの既存ARM64 loader initramfsを追加することに限定する。これにより成功Imageのearly boot、pinctrl/MMCなどの設定のドリフトを防ぐ。

## 製造した未署名候補と実物の同一性

| 要素 | 値 | 根拠 |
|---|---|---|
| 起動成功の署名済み参照P25 | SHA256 `74c1c98b31cdba54f71d16f1983fbeff347bb334c5ae7d7f1353cd57f734936e` | C号機過去のDebian proto2起動実測・owner-private Release |
| 再利用する非圧縮ARM64 Image | SHA256 `141b6750698cb362169cc150974b3464577d6ab5fa98aa941449fc3990c8ad00`、18,921,480B | P25から独立抽出・バイト一致検証 |
| 再利用するDTBセクション | SHA256 `49fc129e2dd7ccc2d2ed4c0c4cac461e33566e2dda164f4ec06d5577baa4286a` | 既知成功の64B AOSP tableとFDTを一切変更しない |
| 新しい独立loader initramfs | SHA256 `a6f4f04170386bb9448acebeb9bafe655f0fd40b8ddb3bfe68ca1251d570b0ba`、3,552,524B | 以前native ARM64 chroot煙試験PASSした元の実物 |
| **新未署名P25** | **SHA256 `54a62dfb4ff4bfb7fb6fbebeae7fe7882375fc0d4822ba38ea2b96d94487847a`**、33,554,432B | [非公開初回製造CI #44898724807](https://github.com/Karin-Laboratory/SBAT6A-Offline-Archive/actions/runs/44898724807) |
| 保存 | [非公開Draft Release 453638868](https://github.com/Karin-Laboratory/SBAT6A-Offline-Archive/releases/tag/untagged-6abd2814477458a33fd7) | 源バイトSHA固定、2回製造のbyte-cmp、独立検査、Release再ダウンロードでSHA/cmp PASS |

- Android boot v2 headerは既知成功の配置からramdisk size/addressとcmdline/boot IDのみを変更。SHA1 boot IDをセクション実物から再計算。kernel_addr=0、dtb_addr=0x01f00000。gzip Imageバイト列・DTBセクションはbyte-identical。
- 原本cmdlineに`rdinit=/init t6_loader=1`を追加し、成功版`console=ttyS0,115200n8`と`keep_bootcon`を保持。
- **外部ramdiskの仮配置アドレスは `0x04000000`（64MiB-relative）**。実際のLinux Image `image_size`、DTBの宣言ロードアドレスとの**数値範囲の非重複**は静的検査済み。ただしLKの物理アドレス基準・予約領域・ramdisk転送実装は未解明なので、**この値はハードウェア互換を保証しない**。
- 参照P25の署名尾部・証明書は一切コピーせず、ファイル末尾はゼロ埋め。source imageの署名検証と、**新未署名P25をLKが認めること**は別ゲート。
- ZIPや公開Releaseは作成しない。参照署名済みイメージ・個体バイナリは**非公開**を維持。

## 静的受入と必要な次段ゲート

1. **完成済みの静的ゲート**：入力実物SHA、32MiBバイト同一性、header差分許可範囲、再計算boot ID、署名余白ゼロ、独立ramdiskのexact SHA・loader marker、2回独立製造cmp、非公開Release再取得の全量照合。
2. **追加検証ゲート**：既知成功カーネル`CONFIG_BLK_DEV_INITRD=y`、`CONFIG_RD_GZIP=y`、`CONFIG_INITRAMFS_FORCE!=y` を実際のImage内IKCONFIGから証明する。Linuxは外部initramfsを組込initramfsの後に展開する想定だが、LKが渡さなければ組込Debian用`/init`が残る。外部の`/init`が実際に選択されるかは本機未検証。
3. **署名前ハードウェア構造ゲート**：LKのAndroid boot v2外部ramdisk転送ロジック、load addressのDDR/予約メモリとの整合、セクションサイズ受理条件の追加監査を行い、未達を残す場合は符号付き承認判断へ明記する。
4. **個別承認を要する後続操作**：新しい完全SHAのowner指定署名、slot A限定の有限試験。G1=Linux初期ログ/loader READY、G2=UART管理、G3=Linux MMC/P26（空でも起動）、G4=LAN2、G5=SSH、順に判定。kexecによるDebian/OpenWrt切替はG1–G5の後。純正slot Bの成功状態は保全。

## バイナリ・開発責任の境界

private源バイト、署名資材、端末固有データを公開しない。製造コードは非公開 `Karin-Laboratory/SBAT6A-Offline-Archive` の `codex/cunit-v10-proven-kernel-loader-pre-sign-20261121` に保存。

本方式は「起動実績のあるImageを守る」ことには成功しているが、**ramdiskを独立セクションとしてLKへ渡すこと自体が新しい変更**。未署名ファイルの製造成功を「起動保証」や「署名許可」と呼ばない。公開Debianの設計憲章v1.4は従来のP44方式であり、独立ローダーv1.0憲章への自動変更は行わない。


## 最終の署名前成果物と厳格ゲート更新（2026-11-21）

- **最終候補の未署名P25** SHA256：`54a62dfb4ff4bfb7fb6fbebeae7fe7882375fc0d4822ba38ea2b96d94487847a`（32MiB、初回CIと同一byte identity）。
- [非公開Draft PR #188](https://github.com/Karin-Laboratory/SBAT6A-Offline-Archive/pull/188) に私有の製造ソースと独立検証器を分離して保存。公開リポジトリにはブートバイナリを含めない。
- **最新の[厳格CI #44898912844](https://github.com/Karin-Laboratory/SBAT6A-Offline-Archive/actions/runs/44898912844) SUCCESS**：既知成功Image実物中のIKCONFIGより、`CONFIG_BLK_DEV_INITRD=y`、`CONFIG_RD_GZIP=y`、`CONFIG_INITRAMFS_FORCE=y`なしを検証。2回独立製造バイト一致、別実装のboot-v2/Android ID/loader marker/unsignedゼロ末尾検査、非公開Releaseから再取得した実物の同一性検査を全PASS。
- **最終Private Draft Release ID `453640260`**、tag `cunit-v10-proven-kernel-loader-unsigned-44898912844`。成果物：`p25-unsigned.img`、`RECEIPT.json`、`SHA256SUMS`。保存後、asset IDから独立に再ダウンロード、SHA256SUMS／`cmp`／完全構造検証PASS。
- 最終ステータス：**UNSIGNED_MANUFACTURE_AND_PRIVATE_READBACK_PASS**。新署名＝**NOT_EXECUTED**、LK非ゼロramdisk実行＝**NOT_TESTED**、物理DDR/予約メモリ互換性＝**NOT_TESTED**、C号機G1–G5＝**NOT_TESTED**。署名許可は発行していない。

製造時にkernel本体を新規buildしていないため、これは成功版のソース再現製造という意味ではなく、**実機成功バイナリの再利用に基づく新しい未署名P25製造**である。機能の証拠と起動の証拠は分ける。


## オーナー個別承認に基づく署名完了（2026-11-21）

- **署名を許可されたunsigned P25 SHA-256:** `54a62dfb4ff4bfb7fb6fbebeae7fe7882375fc0d4822ba38ea2b96d94487847a`、33,554,432B。
- **生成されたsigned P25 SHA-256:** `d259237b1527bfd5702b3ca3193f35f58f80b0b0c9ea67e828d23d3b6bc3d42f`、33,554,432B。
- [保護署名Actions #44900013136](https://github.com/Karin-Laboratory/SBAT6A-Offline-Archive/actions/runs/44900013136)：署名前のSHA・構造照合PASS、self-hosted保護署名器による一度限りの署名PASS、**別プロセスによるRSA-PSS/ROOT→IMAGE証明書チェーン、署名対象body不変性、署名後サイズとSHA・レシート照合PASS**。ただし**最終ジョブ全体はFAIL**。原因はself-hostedランナーに`gh`コマンドがなく、Release保存処理でexit 127となったため。署名の失敗ではない。
- 再署名をせずに、元の保護領域の署名済み実物を再照合するアーカイブ専用ジョブを構築。[非公開アーカイブActions #44900303417](https://github.com/Karin-Laboratory/SBAT6A-Offline-Archive/actions/runs/44900303417) は**SUCCESS**。original unsignedとのbody比較、完全SHA、独立暗号レシートの検証後、GitHub Draft Releaseへアップロードし、両assetを**独立再ダウンロード・バイト比較・SHA一致PASS**。
- **非公開Draft Release ID `453649816`**、tag `debian13-cunit-signed-54a62dfb-44900013136`。署名済みP25 asset ID `775390358`、独立暗号receipt asset ID `775390633`。
- 再取得したレシートのSHA256は `d14e518e3e2e4130e32442dec9c291f0aaedcbf81cfb27d8585967b089bfd359`。出力先は非公開 `Karin-Laboratory/SBAT6A-Offline-Archive` のみ。署名鍵は保護runnerから持ち出していない。
- 新P25の実機LK起動、外部ramdiskロードアドレス`0x04000000`、ローダーinit、P26、LAN2、SSH、kexec切替、Bからの復旧は**今回の署名実行では試験していない**。**実機書込み・slot変更・再起動は一切行っていない**。

**状態：`SIGNED_AND_INDEPENDENT_CRYPTO_READBACK_PASS / HARDWARE_BOOT_NOT_TESTED`。** この署名許可を新しいslot A書込み・実機起動許可とみなさない。以前の失敗P25署名 `886614ed...` との混同、LK外部ramdiskの未検証を隠す記載は禁止。
