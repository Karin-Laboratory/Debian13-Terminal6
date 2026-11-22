# C号機 eMMC 100MHz実機試験

更新日: 2026-11-15 JST

## 適用内容と起動確認

2026-11-15、no-CQE構成を保った署名済みP25へ、MMCノードの `max-frequency = <100000000>` のみを反映して実機適用した。カーネルImage、HS400、bus-width、電圧、その他のDTプロパティは変更していない。

同一C号機で過去に成功した純正 `quec_bootctrl -F` のslot B起動手順を使い、stock Linux 5.4.238で起動した後、PARTNAMEで対象を確認してboot_aのみを書き換えた。32MiB全量のreadback SHA256は候補と一致した。純正 `quec_bootctrl -s 0f 03 00 00 0e 00 01 00` でslot Aへ戻し、Debian 13/Linux 6.18.63の起動とSSH復帰を確認した。

- signed P25 SHA256: `dd9238441761e5896d78bf9553d2d5731ed04bcc6d603bf70a064ba620beabeb`
- 起動slot: A、root: P44 ext4 rw
- live DT: `max-frequency=100000000`、`supports-cqe`なし
- `cmdq_en=0`
- debugfs ios: requested 100,000,000Hz、actual 94,999,965Hz、HS400、8-bit、1.8V
- 管理LAN `lan2=192.168.3.1/24` と `serial-getty@ttyS0` がactive
- 再起動後も上記状態を再確認。UARTはraspi4のUSB-UARTから読み取り専用で起動ログを取得した。リセット操作はしていない。
- P26、P44のraw領域、slot B、GPT、OEM領域には書き込んでいない。P44への変更は以下の専用ファイル試験のみ。

## 15回の直接I/O書込み・読戻し

P44の専用ディレクトリで16/32/64/128/256MiBを各3回実施した。各回でraspi4上の乱数データをC号機RAMへ転送し、P44へdirect I/O書込み、fsync/sync、direct I/O読戻しとSHA256照合を行った。一致したファイルだけ削除してsyncした。

各欄は「書込み+fsync/sync秒 / direct readとSHA256照合秒」。読込み時間にはSSH管理リンク転送が含まれる。

| サイズ | 1回目 | 2回目 | 3回目 | 結果 |
|---:|---:|---:|---:|---|
| 16 MiB | 1.77 / 0.97 | 1.39 / 1.22 | 1.49 / 1.24 | 3/3 SHA一致 |
| 32 MiB | 2.27 / 1.48 | 2.40 / 1.79 | 2.04 / 1.74 | 3/3 SHA一致 |
| 64 MiB | 3.62 / 2.74 | 4.15 / 2.73 | 3.55 / 2.79 | 3/3 SHA一致 |
| 128 MiB | 6.23 / 4.73 | 6.93 / 4.74 | 8.19 / 4.72 | 3/3 SHA一致 |
| 256 MiB | 14.99 / 8.78 | 16.15 / 8.74 | 14.67 / 8.71 | 3/3 SHA一致 |

合計15/15 PASS、1,488MiB。全試験でMMC err_statsは各項目0のまま、新規MMC/CQE/timeout/I/O/ext4エラー行は0件だった。シリーズ中の最高温度は66.421°C。各ファイルは一致確認後に削除し、同時に試験ファイルを保持していない。

## 再起動後の256MiB永続性検証

15回のPASS後に追加の256MiBファイルを書き、再起動前のdirect readback SHA256をraspi4保管元と照合して一致を確認した。ファイルをP44に保持したまま通常再起動し、約21秒後にstrict host-key checkingでSSHが復帰した。再起動後にslot A、100MHz上限、actual 94,999,965Hz、HS400、`cmdq_en=0`、P44 ext4 rw、管理LAN、UART gettyを再確認した。

再起動後のdirect readback SHA256は、raspi4保管元および再起動前読戻しと一致した。MMC err_statsは全項目0、新規MMC/ext4エラーは0件、最高温度66.098°C。検証PASS後にファイルを削除してsyncした。個体情報、乱数ファイルのSHA256、生ログ、UARTログは非公開raspi4記録に保存した。

## 管理接続の再試行記録

slot B起動後、raspi4のC側Ethernetに `192.168.3.71` がまだ割り当てられておらず、その送信元アドレスにbindする最初の5回のSSH接続が失敗した。インターフェースのアドレス復帰後、6回目にstock Bへのstrict SSH接続が成功した。これは一時的な送信元アドレス準備待ちであり、認証失敗やhost key不一致ではない。最終のDebian通常再起動では約21秒後にSSHが復帰し、strict host-key checkingを維持した。host key検証の無効化やネットワーク境界の回避はしていない。

## 評価と残課題

指定された書込み量と一回の再起動永続性試験ではPASSしたため、C号機は100MHz制限・CQE無効を維持する。実測でHS400も維持され、転送クロックは約95MHzだった。

この試験は長期信頼性、寿命、温度/電圧全域、並行負荷時の安定性を証明するものではない。過去の高クロック時エラーの根本原因がクロックだけかどうかも、この負荷試験だけでは確定できない。190MHzへ戻すには別の安全な検証サイクルが必要である。

### 復旧・ロールバック

今回のslot B経由の復旧は同一C号機で実際に再確認済み。必要ならslot Bから純正 `quec_bootctrl -s` を使って既知の署名済みboot_aへ戻す。100MHz候補を戻す場合は保存済みの旧signed P25を使用し、PARTNAME、イメージSHA、全量readbackを確認してからslot Aへ戻す。生ログとバックアップはraspi4の非公開領域に保管し、公開リポジトリには含めない。
