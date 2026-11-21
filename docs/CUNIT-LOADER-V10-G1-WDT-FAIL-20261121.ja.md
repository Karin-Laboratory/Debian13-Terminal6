# C号機 共通ローダーv1.0：G1起動FAIL、EL3→Linux初期起動区間の調査（2026-11-21）

> **状態：実機G1 FAIL。候補f112d3eaはDO_NOT_REUSE/DO_NOT_SIGN、対応する署名済みP25 886614edはDO_NOT_REFLASH。** この文書は失敗証拠の公開可能な要約のみ。生UART・機器固有情報・秘密鍵・実機バックアップは非公開保持。新候補の署名・書込み・再起動は承認していない。

## 実機根拠（受入結果の正本）

- [非公開受入Draft PR #25](https://github.com/Karin-Laboratory/Chappie-Memory/pull/25)、[同ブランチの試験記録](https://github.com/Karin-Laboratory/Chappie-Memory/blob/codex/cunit-loader-v10-acceptance-20261121/terminal6/cunit-loader-v10-acceptance-2026-11-21.md)。
- 署名前 P25 `f112d3eaafc20c983ceed5c750196e9ede7f8e9aaeb49d0676f0746fb09dee58`。**対応する実機署名済みP25** `886614eddaa4e9bddcd6e98914e17509876274daaa1b70639e7c6e95202341ca`（32MiB、boot_a全量readback一致）。
- `lk` がslot Aの署名受理・eMMC/GPT認識・Linux kernel entryへのhandoffを記録。ATFには `Kernel_EL 2`、`Preparing for EL3 exit to normal world`、`el3_exit` が記録された。
- その後**Linux version/banner、initramfs開始、ローダー管理シェルの証拠は一切確認できず**、およそ30秒で `CPU(0) in ATF by WDT` / `HW_WDT`。watchdog時の `PC=0x200` は直接カーネルのfault PCと断定しない。
- 生UART：262,114バイト、SHA256 `0dda7a227a36bf6c8e5af418bdbd35c5001158ece52acc42b2b583547b791a90`、raspi4 `/home/masataka/private/cunit-g1/acceptance-v10-20261121/logs/uart-candidate-v10-20261121.log`。**公開リポジトリには実物をアップロードしない**。
- 有限A試験は終了。純正slot Bへ自動復帰し、B success=1、A retry=0/success=0。純正B ping/known_hostsでの厳格SSH、boot_b SHA一致PASS。P26空ext4はBからfsck clean。P43/P44/GPT/LK/boot_bを変更せず、一時raspi4 aliasを除去、追加再起動なし。

## G1〜G5の今回の正しい判定

| Gate | 判定 | 注記 |
|---|---|---|
| G1 P25単独起動 | **FAIL** | LK/ATF handoffまでPASS、Linux最初の出力が未確認、watchdog発生 |
| G2 UARTシェル | **FAIL（取得のみPASS）** | UART記録の採取はPASS、候補の管理シェル未到達 |
| G3 Linux eMMC/P26 ext4 | **FAIL／部分確認** | LK側MMC/GPT認識とB側fsck cleanのみ。候補LinuxのMMC probe/mount未確認 |
| G4 LAN2 | **NOT_TESTED** | initramfs未到達 |
| G5 SSH | **NOT_TESTED** | initramfs未到達 |
| 安全復帰 | **PASS** | 純正Bの管理LAN/SSH、boot_bとboot-control保持 |

## 原因の境界・仮説

**最初に未検証となる境界はATFのEL3 exit直後からLinux初期consoleまで。** これは`kexec`実行失敗を意味しない。`kexec`にはまだ到達していない。P26 ext4が直接原因である証拠もない。

優先して**オフライン照合する対象**：
1. 既知起動成功の署名済みDebian proto2 P25 `74c1c98b31cdba54f71d16f1983fbeff347bb334c5ae7d7f1353cd57f734936e`と失敗候補のboot-v2 header数値（Image gzip長、kernel/ramdisk/DTB配置、DTB load addr、引数長と有効なearly console指定、AArch64 Image header text_offset/image_size/flags）。両者とも**実物SHA固定**し、差分を示す。差が原因とは限らない。
2. ARM64 early boot kernel config（4KB page/VA geometry、`CONFIG_ARM64_RELOCATABLE`、`CONFIG_RANDOMIZE_BASE`、`CONFIG_EFI`、`CONFIG_PRINTK`、`CONFIG_SERIAL_EARLYCON`、PSCI/EL2、GIC、console選択など）を**起動成功版の実物**と比較。tinyconfigとの差分を無根拠に全て修正しない。
3. 既知成功FDTのSHA一致だけで、新たなImageとのハンドオフ互換性を証明しない。DTB pointer、reserved-memory、bootargs、PSCI/CPU topology、RAM layout、LKが提示したアドレスを検証する。
4. UART原本をハッシュ検証後に読み取り専用で時系列解析し、slot B再起動時のLinuxログと候補slot Aのログを混ぜない。ATF WDTが`Linux version`以前か、ロガーが出力を失った可能性かを分ける。ログは公開しない。

**比較検査の実装先：** [非公開アーカイブ研究ブランチ](https://github.com/Karin-Laboratory/SBAT6A-Offline-Archive/tree/research/cunit-v10-g1-handoff-diff-20261121) に`tools/cunit_v10_g1_handoff_diff.py`を追加し、SHA固定の成功P25と失敗unsigned P25を読み取り専用で比較する。ここで確認した差分と独立調査を経て新しいkernel/profile候補を設計する。

## 次に進む前の禁止・受入ゲート

- **現在の署名済み `886614ed...` を再書込み・再起動しない。** 既知失敗版を「LKを通過したのでP25完成」と扱わない。
- この報告で試験ゲートを再試行しない。**P43/P44、slot B、LK、GPT、boot controlは現状維持**。残置されたboot_aはA retry=0の失敗候補と記録する。
- ソース修正候補には別コミット／別SHA／差分理由／追加のhost-sideテスト／可逆的な復旧計画が必須。成功版へのロールバック資産と純正B、現行C号機P44バックアップ状況を再確認する。
- 新たな署名、boot_a書込み、slot切替、有限起動試験は**具体的候補と前提を示して別途所有者承認が必要**。
- Linux early outputが確認できてからMMC/P26→LAN2→SSHを順に受入。最後にP43→kexec→Debianへ。G1前の`kexec`議論で根本の最初の失敗を覆い隠さない。
