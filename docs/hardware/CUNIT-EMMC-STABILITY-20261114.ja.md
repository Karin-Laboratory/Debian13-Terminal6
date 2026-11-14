# C号機 Debian 13 eMMC障害の解析と限定的な復帰試験

2026-11-14。C号機、Debian 13 arm64、Linux `6.18.63-debian-t6-proto2`、slot A。P44 `rootfs_data` ext4 RW。MMC番号は起動で`mmcblk1`から`mmcblk0`へ変化したため、PARTNAMEとmount元で確認した。P25/P26/純正B/GPT/OEMは未変更。

## 障害と優先仮説

前回の同一bootのkernel logでは、`mtk-msdc 11230000.mmc`が`msdc_cmdq_irq: DATA TIMEOUT ERR`（`dat_err=-110`）を報告し、`mmc1: running CQE recovery`が続いた。その後、P44のWRITE I/O error、ext4のunwritten extent変換失敗、buffer I/O errorが記録された。**MMC側のtimeoutがext4エラーより先行**するが、CQE実装不具合とHS400信号/タイミング不良はこのログだけでは区別できない。再起動の直接原因も未確定。

実測のMMC hostは`11230000.mmc`、8bit、HS400、要求clock 200MHz・actual約190MHz、1.8V。eMMCのEXT_CSDはHS400/HS200/CMDQ対応、Life Time A/B `0x01`、Pre EOL `0x01`。runtime sysfs `cmdq_en=1`。EXT_CSDの`CMDQ_MODE_EN=0x00`表示はツール自身がruntime状態を示さないと注記しており、sysfsを優先した。`cmdq_en`は0444で、稼働中rootfsから書き換える安全な管理口はない。

現在のDTBの`/mmc@11230000`には`supports-cqe`、`mmc-hs400-1_8v`、`mmc-hs200-1_8v`、max-frequency 200MHzがある。対応するLinux 6.18.63 `mtk-sd.c`は`supports-cqe`で`MMC_CAP2_CQE`を立て、CQHCIを初期化する。`mmc.c`はこのcapとcard対応時にCMDQを有効化する。したがって**CQE無効化の最小候補はDTBから`supports-cqe`だけを除くこと**。HS400とclockを維持して比較できる。CQEが根本原因との判定は、この候補の署名・起動・同等負荷試験まで保留。

比較評価:

| 仮説 | 現在の根拠 | 判定 |
|---|---|---|
| CQE経路 | 実際のIRQとrecoveryがCQE経路、runtime有効 | 第一候補。因果未証明 |
| HS400/clock | 実際に約190MHz/HS400 | 第二候補。CQEを切った比較後に評価 |
| 媒体寿命 | EXT_CSD寿命・Pre EOLは低い使用段階 | 重大摩耗を示す証拠なし。媒体不良の否定ではない |
| ext4単独破損 | MMCのtimeoutが先行 | 主因と断定しない。結果としての不整合はあり得る |
| DMA/IOMMU/電源 | 今回識別できる独立カウンタなし | 未解決 |

## 退避と限定試験

raspi4のowner-private領域へP44 rootfsをtar転送。主アーカイブ583,075,840 bytes、SHA-256 `06017b9b54faf0fe3b1330faa37a5be551a7c6ea86097b9dd9331e2fbde5dedf`。`/proc`/`/sys`/`/dev`/`/run`/`/tmp`と変化しやすい`/var/log`/APT archiveは除外し、後二者は補助tar（SHA-256 `1bb8e6197c22057941914ef08c3f0b197a72ec2844a058ada3b292df115a1086`）に保存。主tarはSHA確定、全エントリ走査、隔離ディレクトリへの試験展開、`/etc/ssh`・dpkg DBなど重要パスの復元を確認。これはファイルレベル退避でありext4 journalや空き領域のイメージではない。生データはGitHubに置かない。

現行CQE/HS400設定で専用P44ディレクトリへ4KiB、1MiB、8MiB、16MiBを順次書込み。各段で`conv=fsync`、`sync`、direct I/O読戻しのSHA一致を確認。既存のMMC/ext4関連log件数16→16。`dpkg --audit`空、`dpkg -V`差分なし。APT update成功、`hello` 2.10-5（52.7KiB）を新規導入して実行・`dpkg -V hello`成功。導入後の`sync`も成功し、同件数16→16。

単回再起動後、Debian slot A、P44 ext4 RW、管理LAN ping 2/2、strict SSH、Wi-Fi `phy0`が復帰。試験ファイル4件の全SHAと`hello`の実行・dpkg検証を再確認。新bootのMMC/ext4関連log件数0。UARTは単一picocomで記録後に解放した。**今回の約25MiBの順次書込みと小さなAPT導入で再発しなかった**という範囲の結果であり、前回の複数パッケージ導入と同一負荷での長期安定性は未実証。

再起動後にNAT側のDNS解決とAPT updateも再実行して成功。`sync`後も新bootのMMC/ext4関連log件数0、SSH・boot-success・Wi-Fi PHY unitはactive。runtime CQEは依然有効なので、これはCQE無効化候補の検証結果ではない。

試験SHAのprivate receiptをraspi4に保存後、専用テストファイル4件とディレクトリを削除し、再度`sync`。新bootのMMC/ext4関連log件数は0のまま。RAM上の元データとESP32 probeも再起動により消失したことを確認。

## CQE無効化候補（未署名・未フラッシュ）

公開スクリプト`tools/prepare-cunit-no-cqe-dtb.sh`で、固定SHAのprivate DTBから`supports-cqe`だけを削除。DTSへ逆変換した全内容の差分はその1行のみ。新DTB 148,753 bytes、SHA-256 `fb20c141ef71833cac20cd1deb13161c338ceac41843ad94fb5c81f4e1f0f6e9`。

`tools/assemble-cunit-cqe-off-p25.py`で、固定済み旧unsigned P25を同一材料でバイト一致再製造できることを確認後、DTB sectionとboot-v2 ID/sizeのみを更新。新unsigned P25 33,554,432 bytes、SHA-256 `765f48ebe06bd69adb63a1ad83bdabe8edf16f15a6dc461f379fa5708a62d1f0`。別プロセスでkernel gzip/Image、vendor64、DTB、boot-v2 ID、padding、全量SHAを確認した。owner-private保存。署名、P25書込み、起動試験は**未実施**。

この候補の実機A/B比較には、上記SHAへのprotected signingとC号機P25差替えについて別承認が必要。純正B復旧経路、現signed P25、P44 backupの所在とハッシュを実行前に再確認する。CQE offで失敗が続く場合はHS400/clockを次候補にする。オンラインrootfsの修復fsckやruntimeの未対応CQE切替は行わない。

承認待ちの復旧準備として、現C号機の`PARTNAME=boot_a`は32MiBで、全量SHA-256 `7e2bf08e2aeaa84a70d2d8c30490ebc5628fb89aba803d8fec5bb4481259531b`。owner-privateに保存された既存signed P25の2コピーも同SHAであることを照合した。現bootctrlはA priority15/retry0/success1、B priority14/retry0/success1。候補試験時は既知のslot B管理経路とUARTを先に再確認し、旧signed P25を使った復帰可能性を保持する。今回この状態は変更していない。

## OpenWrtへの還元

Linux 6.18系MediaTek MMC/MT6990の同じDT propertyとCQE経路を使用する場合、`supports-cqe`を外した比較候補を作り、HS400条件を固定して独立検証する。今回のDebian実測だけでOpenWrtへ恒久反映しない。
