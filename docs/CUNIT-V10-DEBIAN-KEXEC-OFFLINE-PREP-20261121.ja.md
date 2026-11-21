# 共通ローダーv1.0 → Debian 13: 実機に触れない準備記録（2026-11-21）

状態: **SOURCE-ONLY CANDIDATE / NO HARDWARE ACCESS / NO NEW BINARY RELEASE**。
本ブランチは [PR #43](https://github.com/Karin-Laboratory/Debian13-Terminal6/pull/43) の source commit `225417fe0d8404df07b23098fc784878b64fa685` から分離し、進行中のC号機試験を妨げない。実機のP25/P26/P43/P44、raspi4、起動slot、署名鍵、Release、既存PRを変更しない。

## 確認できた実績と元資産

- 共通ローダーP25のunsigned候補は `f112d3eaafc20c983ceed5c750196e9ede7f8e9aaeb49d0676f0746fb09dee58`。署名済み実物のSHAと実機PASSは本準備作業では未確認。
- 実機で起動実績のある**旧Debian専用P25**の署名済みSHAは `74c1c98b31cdba54f71d16f1983fbeff347bb334c5ae7d7f1353cd57f734936e`、Linux `6.18.63-debian-t6-proto2`。これは新ローダーP25と**別物**。
- 旧proto2対応の非公開 [P44-install.zip](https://github.com/Karin-Laboratory/SBAT6A-Offline-Archive/releases/tag/untagged-277acdede20c8efeb442) は 178,516,940 bytes、SHA256 `9aded7613ffc262060501d633dd2d27600a544b5fd7d35a6bdbeb25ff9b28f09`。製造・再取得検証は過去のCIでPASSだが、C号機現行P44と同一ではない。新ローダーとの組み合わせは未実機検証。
- 既存 `105` module archiveは `cfg80211/mac80211` が欠ける。必要な場合はPR #41で検証済みのframework + MT76 3モジュールを**同一ABI・出自の組合せとして**扱い、vermagicだけで合格にしない。
- 成功版P25のboot v2からLinux Image/DTBを取り出す方法を採用する場合、署名・ヘッダー・DT tableの区分を守り、**imageとboard.dtb実物の独立SHAが確定するまで**P43成果物と呼ばない。新ローダー内蔵DTBを第2段Debian DTBとして流用しない。

参照: Chappie-Memory `terminal6/CUNIT-DEBIAN-P25-P44-ROLLBACK-PIN-20261121.md`、PR #41/#43、private Release ID 452383911 / 453404685。

## 仕様の差分を勝手に変更しない

2026-11-21確定仕様v1.0は「OS別パッケージにImage/DTB/initramfs/rootfs tar等をまとめ、P43の `terminal6/<OS>/` ディレクトリを標準のrootfs場所とし、P44は任意」としている。一方、旧Debian憲章v1.4とユーザー指定の**今回の実証**はP44上の現存Debian rootfsを対象とする。従って、今回のP44起動は**移行試験専用の互換プロファイル**であり、公開配布レイアウトの最終決定ではない。憲章・確定仕様・AGENTS.mdを自動変更しない。

## オフライン製造前検証（個体操作不要）

入力 `Image`、`board.dtb`、旧proto2 P44 candidate ZIP（任意 `initrd.img`）が私有の信頼済み環境に取得できた場合に、次を実行する。

```bash
python3 scripts/stage-v10-debian-kexec-offline.py \
  --image /private/verified-proto2/Image \
  --dtb /private/verified-proto2/board.dtb \
  --p44-zip /private/verified-proto2/P44-install.zip \
  --output /private/new-v10-kexec-stage
```

このスクリプトは**デバイスにアクセスしない**。ARM64 Linux Imageヘッダー、FDTマジック/長さ、既存ZIPの全体SHA・CRC・内部tarのSHA・旧P25とのmanifest対応を検査する。P43用の `terminal6/debian/Image` と `board.dtb` のコピー、manifest、SHA256SUMS、boot設定テンプレートを出力する。既存の出力先には上書きしない。入力のImage/DTB自体の正本SHAを非公開ledgerへ記載すること。**構造的妥当性は起動互換性を保証しない**。

必須注意: `debian.conf.EXAMPLE` の `cmdline` は意図的に未確定。過去成功版の `console=ttyS0,115200n8` やP44の `PARTNAME` を根拠なく補完しない。現物のパーティションと旧成功ログ・initrd要否を確認後、別途ゲートで確定する。 `boot.conf.EXAMPLE` は安全のため `autoboot=0`。

## 実機作業に進むための明確なゲート

| Gate | 現時点 | 必要な証拠 |
| --- | --- | --- |
| A1 候補資産の所在・過去の保存証拠 | PASS（メタデータのみ） | 非公開Release、PR #41、復旧台帳 |
| A2 正確なImage/DTB/モジュールの独立バイト照合 | BLOCKED | 私有環境でアセット取得・SHA照合 |
| B0 新P25のUART/eMMC/LAN2/SSH 5項目 | NOT_TESTED（本作業では） | 別セッションの実機受入レポート |
| B1 P43の実配置とread-only読出 | NOT_TESTED | PARTNAME/ext4/ファイルSHA |
| B2 `kexec -l` | NOT_TESTED | UART・ロード結果 |
| B3 Debian第2段Kernel | NOT_TESTED | UARTログ |
| B4 P44 rootfs | NOT_TESTED | mount/fstab/互換性 |
| B5 Debian LAN/SSH | NOT_TESTED | SSH遠隔コマンド結果 |
| C1 新v1.0配布ZIP | BLOCKED | 実機成功構成と最終レイアウト決定 |
| C2 新ZIPの独立保存とreadback | NOT_TESTED | 完成ZIPのSHAとprivate Release再取得 |

### 実機受入前の危険条件

1. `initramfs/terminal6-boot` は `/userdata` に **P43 ext4 ro,noload** がマウント済みであることを要求し、最終段でunmountする。P43が別FSの場合は変更せずBLOCKEDとする。
2. 旧proto2 kernelのinitramfs内P44マウント依存、第二段へのkexec時のMMC/clock/CPU初期化、DTB memory-reserved-regionを改めて確認する。
3. 旧P44-install.zipのrootfsは初回用の無認証SSH経路を含む。既存C号機P44へ勝手に展開しない。LAN2は物理隔離し、ホスト秘密鍵・資格情報を保持する。
4. G1-G5のPASS確認前は `kexec -l` / `kexec -e`、P26/P43/P44変更、slot変更、再起動を実施しない。
5. P25専用ローダーはP44を要求しないが、**第2段DebianはP44が存在して正しくマウントできなければ起動しない**。混同しない。

## この準備ブランチの成果範囲

このブランチはsource-onlyであり、既存PR #43の共通ローダーやPR #41の旧P44製造ルートを変更しない。**新しいP44.zipの実製造、Image/DTBの独立SHA、非公開Releaseへのアップロードは、本ブランチだけでは完了しない**。次に行うのは非公開ビルド環境で私有の成功版Image/DTBを取得・独立検証して、上記ステージングスクリプトと試験で仕上げる工程である。


## 2026-11-21 非公開実製造成果（実機操作なし）

- 非公開製造ソース: `SBAT6A-Offline-Archive` branch `codex/v10-debian-kexec-private-manufacture-20261121`、製造ジョブ [#44886374294](https://github.com/Karin-Laboratory/SBAT6A-Offline-Archive/actions/runs/44886374294)。
- **非公開Draft Release保存・再取得SHAと全バイトcmp: PASS**。保存先 [private Draft Release](https://github.com/Karin-Laboratory/SBAT6A-Offline-Archive/releases/tag/untagged-fa7e82f4efb2f0eb4610) (Release ID `453556881`)。
- 検証済み入力: 旧署名済みP25 `74c1c98b31cdba54f71d16f1983fbeff347bb334c5ae7d7f1353cd57f734936e`、旧P44 ZIP `9aded7613ffc262060501d633dd2d27600a544b5fd7d35a6bdbeb25ff9b28f09`。
- 旧P25 boot-v2のkernel gzipと1-entry AOSP DT tableから独立抽出した Image SHA256 **`141b6750698cb362169cc150974b3464577d6ab5fa98aa941449fc3990c8ad00`** (18,921,480 bytes)、DTB SHA256 **`a6bef90e18c0a16934e6c4196fea60408a1fed08b6ef9b62c7fbe5d7c5632d91`** (148,753 bytes)。Linux `6.18.63-debian-t6-proto2`。
- `P43-debian-kexec.zip`: **19,072,579 bytes** SHA256 **`60437aad2f26654648b0c0df022d364bf3c5d861414c6fc74a8da69965a5bccc`**。
- `P44-install-v10-kexec-candidate.zip`: **197,581,135 bytes** SHA256 **`b40faae5fb46ac3fe073005fb9d6db5edd5e69bc86bdbadd274fa16ff7da084c`**。旧proto2 rootfs・module tarと第2段起動資産を同梱する**C号機P44互換試験候補**。v1.0標準のP43 rootfs配布方式とは別で、OS移行用の暫定構成。
- `BUILD-RECEIPT.json` SHA256 `b2c787e46f949dff0d26c86f28cd9a254953036dba6010d992a0bdf529c56bc3`。公開ZIPの配布許可はなく、非公開保全のみ。
- ビルドの製造・Release再取得・ZIP内部CRC/SHA・入力照合はPASS。**Actions run全体はFAIL**: 補助的な `actions/upload-artifact@v4` がArtifact storage quota超過で失敗。製造と非公開Releaseの独立再取得はその前にPASSしている。余分なArtifact保存を後続workflowから除去。
- **実機kexec/P44 mount/LAN/SSHはNOT_TESTED**。boot.confは `autoboot=0`、debian.confは未確定の `cmdline` テンプレートのみ。P43/P44実機書込みや再起動は実施していない。

### 更新したゲート

| Gate | 状態 |
|---|---|
| A1 旧資産独立再ダウンロード・全体SHA | PASS |
| A2 第2段Image/DTB抽出・実バイナリSHA | PASS |
| C1 P43/P44互換候補ZIP実製造 | PASS (private candidate only) |
| C2 非公開Draft Release保存・独立SHA/cmp | PASS |
| B0-B5 実機P25受入/kexec/Debian起動 | NOT_TESTED (別セッションに委ねる) |
| C-final 標準P43 rootfs方式・公開配布判定 | BLOCKED |

**次の作業で注意**: 成功版P25のembedded initramfsと `root=` などのコマンドラインを実機ログ・過去の正本と照合するまで、kexecに渡すコマンドラインを推測して埋めない。再パッケージ化済みZIPの存在は実機互換性を意味しない。
