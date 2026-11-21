# C号機共通ローダーv1.0：外部ramdisk導入後のLK FDT ASSERTと対処案（2026-11-21）

## 実機G1：署名は通過、Linux前に停止

- 対象：signed P25 `d259237b1527bfd5702b3ca3193f35f58f80b0b0c9ea67e828d23d3b6bc3d42f`、unsigned原本 `54a62dfb4ff4bfb7fb6fbebeae7fe7882375fc0d4822ba38ea2b96d94487847a`。
- boot_aへ33,554,432B書込み・全量SHA readback一致。LK署名検証PASS。
- LKログ：`mrdump_debug_kinfo_fdt_setup:166 Error: fdt_add_subnode failed offset=0xfffffffe`、`ASSERT platform/mediatek/common/aee/mrdump_setup.c:167`、その後停止・watchdog。Linux banner、initramfs `/init`、UART/SSHローダー管理へ**未到達**。
- `0xfffffffe` は符号付きで `-2`、libfdt の `-FDT_ERR_EXISTS` 相当。しかし**追加対象ノード名と重複経路は実機ログだけでは未確定**。
- slot A有限失敗後純正B自動復帰、B ping/厳格SSH成功、boot_b SHA不変。P26/P43/P44/GPT/LKは書換えなし。別セッションへのC号機引継ぎが可能になった。
- 原本証拠：非公開 [PR #43実測コメント](https://github.com/Karin-Laboratory/Debian13-Terminal6/pull/43#issuecomment-7063204183)。生UART 575,532B SHA `6b6ce70bb3f65fb2c32c44d9499ae6174da78fadff70459368b8b57b5d52dd4a` はraspi4非公開領域のまま保持。機器固有データをGitへ公開しない。

## 実物オフライン解析：入力FDT重複なし

[非公開CI #44909084128](https://github.com/Karin-Laboratory/SBAT6A-Offline-Archive/actions/runs/44909084128) が、GitHub owner-private ReleaseのSHA固定実体を取得し、boot-v2/FDTの入力を読み取り専用で比較、**SUCCESS**。

| 検査 | 起動成功P25 | G1失敗候補 |
|---|---|---|
| P25 SHA256 | `74c1c98b...` | `54a62dfb...` |
| gzip kernel section | 9,299,877 bytes | **同じ9,299,877 bytes** |
| 外部ramdisk | **0 bytes** | **3,552,524 bytes** |
| boot-v2 ramdisk_addr | `0x01000000`（未使用） | `0x04000000` |
| DTBセクションSHA | `49fc129e2dd7...` | **同じ** |
| 実FDT SHA | `a6bef90e18c0...` | **同じ** |
| FDTノード | 851 | 851 |
| 入力FDTの重複ノードパス | 0 | 0 |

従って**「失敗候補の静的DTB中に同名ノードが2個ある」が原因という説明は成り立たない**。LKの実行時FDT加工中の重複、分岐差、または別DTBを処理している可能性は残る。外部ramdiskの新規導入が差分だが、その因果も確定ではない。

## 改善仮説と最小化した次候補

実機成功版Image/DTBを維持した「外部ramdisk」のみ新設する方式を、一旦停止する。LKがその追加によって従来と違うFDT処理を行った可能性を切り分ける。

**次候補：ローダー用gzip/newc initramfsをARM64 Linux Image内へ組込む方式。**

- 起動成功版**実物Imageから抽出したIKCONFIG**を、保存済みC号機KVM kernel source snapshotに適用してビルド。元ビルドのsource snapshotは厳密なImageバイト再現でない点を明記。
- `CONFIG_INITRAMFS_SOURCE`だけ既存private loader cpio（SHA256 `a6f4f04170386bb9448acebeb9bafe655f0fd40b8ddb3bfe68ca1251d570b0ba`）へ変更。
- boot-v2の**ramdisk_size=0**、元ramdisk_addr=`0x01000000`（未使用）を維持。FDTセクションの全バイト、cmdline、kernel/dtbアドレスも元のまま。
- 変わるのは**再コンパイルされたカーネルgzipとboot ID**のみ。元カーネルとバイト同一とは言えない。LKのFDT再処理が修復されたことは次の実機試験まで未確認。
- boot-critical Kconfig driftをfail-closed検査、二度のunsigned P25製造結果と別検証器のバイト比較を必須とする。最終成果物・SHA・receiptを非公開Draft Releaseへ保存、再取得全量照合。
- 予定ソース：[非公開Draft PR #189](https://github.com/Karin-Laboratory/SBAT6A-Offline-Archive/pull/189)、Actions [#44909418320](https://github.com/Karin-Laboratory/SBAT6A-Offline-Archive/actions/runs/44909418320)。

## 安全境界

- 実機の次回署名済候補は**新しい完全SHA**に限定。今回G1 FAILのsigned `d259237b...` と前回FAIL `886614ed...` の再署名・再試験は実施しない。
- この変更はコード・ホストCI・私有成果物の整理のみ。**署名・boot_a書込み・slot切替・再起動・P26/P43/P44変更・公開配布は行わない**。
- 仮に製造CIがPASSしても、LKのMRDUMP FDT処理、Linux初期表示、内蔵ローダー`/init`、MMC・管理LAN/SSH、後段kexecは**実機 NOT_TESTED**。
- ①共通ローダーと②Debian13単独版は別SHA・別受入ゲート。現在のC号機の排他使用権を妨げない。
