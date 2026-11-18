# C号機 初回管理SSH/IPとP25安定基礎設計憲章の整合確認

記録日：2026-11-18 JST／状態：**設計レビュー・差分記録。実機SSH/ARP未検証。憲章自体は未改定**。

## 適用した正本

- [設計憲章 v1.0](../P25-FOUNDATION-POLICY.ja.md)：`main` commit `ab0bd832d03d3ad47a2531a256ae9d26f34ffc0a`、blob `3f79fa3447808c2f9bfd5ee07a214171f160d4c0`。**本文をそのまま本ブランチにも取り込んだ。**
- [AGENTS.md](../../../AGENTS.md)：`main`同版を原文のまま取り込み（blob `6d7d29d08a9445d62c3665f761d5918c56975134`）。
- [管理P25 PR #25](https://github.com/Karin-Laboratory/Debian13-Terminal6/pull/25) と[製造Runbook](../../CUNIT-STABLE-MANAGEMENT-P25-RUNBOOK-20261118.ja.md)、[純正B読み取り調査 PR #27](https://github.com/Karin-Laboratory/Debian13-Terminal6/pull/27)（別Draft。stock Bの今回実測と本候補の差を判定）。
- これは**憲章の改訂提案ではない**。実装上の説明・選択・未達の整理であり、憲章変更には所有者の別途明示承認を必要とする。

## 所有者の現在の希望（受入目標）

1. C号機の個体専用鍵が最初から用意され、**初回起動後に `ssh root@192.168.1.1` がTCP/22でパスワード入力なしに成功する**。意味はrootのEd25519公開鍵認証。空パスワードの許可ではない。
2. 初期IPはOpenWrt標準に合わせ `192.168.1.1/24`。隔離された管理接続で使用。家庭LANに接続する場合は重複しないアドレス/セグメントへ移行。
3. P25は起動・ストレージ・初期有線管理・復旧に必要な最小限にとどめ、Wi-Fi、Bluetooth、GNSS、USB等の機能とモジュールは可能な限りP44側で追加。カーネル/DTB変更が必要なら安全にP25を再製造可能とする。
4. 製造済み鍵なしP25は保管実績として扱うが、上記目標を満たす実用版と混同しない。

## 憲章との対応と差異

| 項目 | 憲章の規定 | 現状・差分 | 判定と対処 |
| --- | --- | --- | --- |
| P25/P44役割 | §§2,4,5：最小の起動・管理・復旧、追加機能はP44。P25更新を禁止しない | PR #25はbuilt-in NETSYS/DSA/PCS一式を固定選択、KVM等のcapable構成を流用 | **条件付き整合**。built-inは今回の検証対象であり唯一の恒久方針ではない。代替として同一initramfs内ABI一致モジュールを許容。機能/容量は起動・管理に劣後 |
| root SSH認証 | §6：root公開鍵認証、鍵が無ければfail-closed | 公開/非公開保管済みunsigned P25にC号機個体鍵なし。P44 rootfsにもログイン公開鍵が自動登録される保証はない | **BLOCKED**。raspi4側秘密鍵は動かさず、公開鍵/個体ホスト鍵を非公開工程でP25・P44の双方へ整合した方法で配置。受入前に鍵真正性検証 |
| SSH TCP/22の統一 | §6：通常SSH・救援SSHの鍵/port/known_hosts/handoffを明記 | Debian通常SSHは22、initramfs救援Dropbearは2222。P44成功前のSSHは起動せず、P44の通常ssh.serviceはroot鍵を継承しない場合がある | **所有者目標は未達**。早期TCP/22接続・通常P44 SSHへの引継ぎ設計を別ゲートで実装/検証。再起動・失敗ケースと、同一IP/portのSSHホスト鍵相違を解消するまで「初回SSH PASS」としない |
| 初期アドレス | §6：旧`192.168.3.0/24`は隔離試験の履歴、家庭LAN`192.168.0.0/22`との重複を解消 | 新初期値は`192.168.1.1/24`。憲章に初期IPの固定指定はない。静的IP注入は鍵/隔離フラグが揃ったP44のRAM設定のみ | **憲章とは矛盾しない**。旧値は履歴に残し、初期値を[単一設定](../../../configs/cunit-initial-management.cidr)で管理。家庭LANへの直結禁止、移行前再設計。raspi4旧`192.168.3.71/24`も同一セグメントへ変更が必要 |
| 公開ドライバと有線通信 | §§3,4,7：実RX/TX、ARP/IP、SSHで管理ゲート合格 | [PR #27](https://github.com/Karin-Laboratory/Debian13-Terminal6/pull/27)の純正B実測は`eth0.1/.2`→`br-lan`、`eth1` DOWN・`lan2`なし。候補は`eth1`+`lan2`前提 | **最大の技術BLOCKER**。同じ物理ポートがpublic P25経路で動くという証拠がない。IPだけ変更しても解決しない。DT/MAC/PCS/DSA実測→UART→carrier→双方向ARP/IP→SSHが必須 |
| eMMC安定性 | §§3,4,7：100MHz/no-CQE等を回帰検証 | 過去の別ビルド実績のみ。本候補の長期安定は未測定 | **NOT_TESTED**。P44 I/O整合・再起動・復旧実測まで完成宣言不可 |
| P44モジュール | §5：同一ビルド/同一ABI、symbol/CRC/依存/firmware実動作 | 40 `.ko` のvermagicと同一ビルド出力を検証済み。実insmod/modprobeとハード動作は未実施 | **製造PASS、機能NOT_TESTED**。ABI/依存/firmwareと実ロードを別試験 |
| 署名・機器操作 | §§7–10：入力SHA単位の承認、純正B保全 | 鍵なし非公開P25は32MiB SHA確認・保管済み。新IPソース更新後の出力は別SHAになる | **署名・書込み権限なし**。既存SHAの承認を流用せず、鍵個体化後の別ファイルで独立SHA・非公開保全と承認が必要 |

## 暫定実装の扱い

- [初期管理CIDR](../../../configs/cunit-initial-management.cidr)が`192.168.1.1/24`の正本。現在の`initramfs-rescue.sh`はこの静的IPを使用。P44には所有者の個体鍵と隔離フラグが揃った場合のみ`/run/systemd/network/10-cunit-isolated-management.network`を一時生成する。**これだけでは初期TCP/22、実NIC到達、P44 SSHの鍵登録を保証しない。**
- 憲章が認める早期LANの内蔵・initramfsモジュール選択を尊重する。現在のbuilt-in Kconfigチェックは**今回の候補の試験契約**であり、原則的な`=y`強制に格上げしない。
- 救援SSHはP44ルートマウント失敗時・handoff後のネットワーク故障時で実行可否が異なる。`switch_root`後のsystemd障害ではUART/純正Bが現実の復旧経路で、常時救援と称さない。
- [ハードウェア設計PR #27](https://github.com/Karin-Laboratory/Debian13-Terminal6/pull/27)は別Draftであり、調査の未確認箇所やFirmware `1.00.10`／先行記録`1.01.80`の不整合も保存。検証前に一方を正しいと断定しない。
- 過去の鍵なし保存P25（private Draft Release ID 449370879 / SHA256 `353533d88ff76b22cb324ec95230ed6bf2da683026a1a227a7c5fbcecc1e9a2b`）は**この新IP変更の前のもの**。新設定・鍵・TCP/22は反映されていない。
- **NO_SIGN / NO_FLASH / NO_SLOT_CHANGE / NO_REBOOT / NO_RF**。憲章・AGENTSの取り込み以外にmainを変更しない。本決定記録はDraft PR #25でレビュー。

## 次の受入ゲート

1. 公開OSS根拠をもつ`eth0/eth1`・SGMII/DSA物理ポート対応とARP実測。P25書込みなしの静的調査は先行可。実機候補試験は別承認を得る。
2. 個体専用の公開鍵／ホスト鍵の非公開注入と、initramfsからP44通常sshdへのkey・port・known_hosts継続設計を検証。rootパスワード・空パスワードは使わない。
3. 別SHAのunsigned P25 + P44対応資産を独立製造・保全し、署名・実機試験は所有者の別途承認。
4. 隔離`192.168.1.0/24`上で`ssh root@192.168.1.1`を最初から受け付け、P44移行後も公開鍵認証できることを実測してから、初回管理SSHをPASSとする。
