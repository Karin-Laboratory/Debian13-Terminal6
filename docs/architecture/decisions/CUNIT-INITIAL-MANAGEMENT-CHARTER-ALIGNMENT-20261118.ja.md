# C号機 初回管理SSH/IPとP25安定基礎設計憲章の整合確認

> **履歴専用・最新版ではない:** この記録は2026-11-18の設計憲章v1.0時点の判断。所有者はその後に憲章 **v1.2** を制定し、**物理隔離した空P44で初回無認証root SSH(TCP/22)**を明示採用した。したがって本文中の「初回から公開鍵必須」「初回無認証は不採用」という趣旨は**失効**。最新版は[憲章v1.2](../P25-FOUNDATION-POLICY.ja.md)と[新決定記録](CUNIT-CHARTER12-INITIAL-SETUP-AND-PAIR-BUILD-20261118.ja.md)を正本として扱う。

記録日：2026-11-18 JST／状態：**所有者が矛盾①を許容、②③は憲章準拠と明示決定。実機SSH/ARP未検証。憲章自体は未改定**。

## 適用した正本

- [設計憲章 v1.0](../P25-FOUNDATION-POLICY.ja.md)：`main` commit `ab0bd832d03d3ad47a2531a256ae9d26f34ffc0a`、blob `3f79fa3447808c2f9bfd5ee07a214171f160d4c0`。**本文をそのまま本ブランチにも取り込んだ。**
- [AGENTS.md](../../../AGENTS.md)：`main`同版を原文のまま取り込み（blob `6d7d29d08a9445d62c3665f761d5918c56975134`）。
- [管理P25 PR #25](https://github.com/Karin-Laboratory/Debian13-Terminal6/pull/25) と[製造Runbook](../../CUNIT-STABLE-MANAGEMENT-P25-RUNBOOK-20261118.ja.md)、[純正B読み取り調査 PR #27](https://github.com/Karin-Laboratory/Debian13-Terminal6/pull/27)（別Draft。stock Bの今回実測と本候補の差を判定）。
- これは**憲章の改訂提案ではない**。実装上の説明・選択・未達の整理であり、憲章変更には所有者の別途明示承認を必要とする。

## 所有者の現在の希望（受入目標）

**2026-11-18最終判断：初期IP重複の注意①は了承。②SSHと③LANドライバ方式は憲章第4・6節に揃え、「起動前から22番」「built-in一択」の追加要件は採用しない。**

1. C号機の個体専用鍵が事前に用意され、**P44のDebianが起動して通常SSHが待受を開始した時点から、`ssh root@192.168.1.1` がTCP/22でパスワード入力なしに成功する**。これはrootのEd25519公開鍵認証であり、空パスワードを許さない。P44起動前からTCP/22でSSHを提供することは**求めない**。P25/initramfsの救援SSHは障害時用の別経路（現候補はTCP/2222）。
2. 初期IPはOpenWrt標準に合わせ `192.168.1.1/24`。隔離された管理接続で使用。家庭LANに接続する場合は重複しないアドレス/セグメントへ移行。
3. P25は起動・ストレージ・初期有線管理・復旧に必要な最小限にとどめる。**管理LANはbuilt-inまたは同一P25のinitramfs内の互換モジュールのどちらでもよく、方式を固定しない。** Wi-Fi、Bluetooth、GNSS、USB等の機能と追加モジュールは可能な限りP44側で開発する。カーネル/DTB変更が必要なら安全にP25を再製造可能とする。
4. 製造済み鍵なしP25は保管実績として扱うが、上記目標を満たす実用版と混同しない。

## 憲章との対応と差異

| 項目 | 憲章の規定 | 現状・差分 | 判定と対処 |
| --- | --- | --- | --- |
| P25/P44役割 | §§2,4,5：最小の起動・管理・復旧、追加機能はP44。P25更新を禁止しない | PR #25はbuilt-in NETSYS/DSA/PCS一式を固定選択、KVM等のcapable構成を流用 | **条件付き整合**。built-inは今回の検証対象であり唯一の恒久方針ではない。代替として同一initramfs内ABI一致モジュールを許容。機能/容量は起動・管理に劣後 |
| root SSH認証 | §6：root公開鍵認証、鍵が無ければfail-closed | 公開/非公開保管済みunsigned P25にC号機個体鍵なし。P44 rootfsにもログイン公開鍵が自動登録される保証はない | **BLOCKED**。raspi4側秘密鍵は動かさず、公開鍵/個体ホスト鍵を非公開工程でP25・P44の双方へ整合した方法で配置。受入前に鍵真正性検証 |
| 通常SSH・救援SSHの分離 | §6：通常P44 SSHとinitramfs救援SSHは役割を分け、鍵/port/known_hosts/起動・停止条件を明記 | Debian通常SSHはTCP/22、救援DropbearはTCP/2222。通常SSHのroot公開鍵はP44へ事前配備が必要。救援はinitramfsまたは一時RAMサービスで障害時に利用 | **設計整合／実利用は未達**。早期TCP/22への統一は不要。P44の初回通常SSH公開鍵認証と、障害時2222番への鍵・host key・known_hosts/待受継続を**別々に実測**してからPASSとする |
| 初期アドレス | §6：旧`192.168.3.0/24`は隔離試験の履歴、家庭LAN`192.168.0.0/22`との重複を解消 | 新初期値は`192.168.1.1/24`。憲章に初期IPの固定指定はない。静的IP注入は鍵/隔離フラグが揃ったP44のRAM設定のみ | **憲章とは矛盾しない**。旧値は履歴に残し、初期値を[単一設定](../../../configs/cunit-initial-management.cidr)で管理。家庭LANへの直結禁止、移行前再設計。raspi4旧`192.168.3.71/24`も同一セグメントへ変更が必要 |
| 公開ドライバと有線通信 | §§3,4,7：実RX/TX、ARP/IP、SSHで管理ゲート合格 | [PR #27](https://github.com/Karin-Laboratory/Debian13-Terminal6/pull/27)の純正B実測は`eth0.1/.2`→`br-lan`、`eth1` DOWN・`lan2`なし。候補は`eth1`+`lan2`前提 | **最大の技術BLOCKER**。同じ物理ポートがpublic P25経路で動くという証拠がない。IPだけ変更しても解決しない。DT/MAC/PCS/DSA実測→UART→carrier→双方向ARP/IP→SSHが必須 |
| eMMC安定性 | §§3,4,7：100MHz/no-CQE等を回帰検証 | 過去の別ビルド実績のみ。本候補の長期安定は未測定 | **NOT_TESTED**。P44 I/O整合・再起動・復旧実測まで完成宣言不可 |
| P44モジュール | §5：同一ビルド/同一ABI、symbol/CRC/依存/firmware実動作 | 40 `.ko` のvermagicと同一ビルド出力を検証済み。実insmod/modprobeとハード動作は未実施 | **製造PASS、機能NOT_TESTED**。ABI/依存/firmwareと実ロードを別試験 |
| 署名・機器操作 | §§7–10：入力SHA単位の承認、純正B保全 | 鍵なし非公開P25は32MiB SHA確認・保管済み。新IPソース更新後の出力は別SHAになる | **署名・書込み権限なし**。既存SHAの承認を流用せず、鍵個体化後の別ファイルで独立SHA・非公開保全と承認が必要 |

## 暫定実装の扱い

- [初期管理CIDR](../../../configs/cunit-initial-management.cidr)が`192.168.1.1/24`の正本。現在の`initramfs-rescue.sh`はこの静的IPを使用。P44には所有者の個体鍵と隔離フラグが揃った場合のみ`/run/systemd/network/10-cunit-isolated-management.network`を一時生成する。**これだけではP44起動後の通常TCP/22、実NIC到達、P44 SSHの鍵登録を保証しない。起動前のTCP/22は要求しない。**
- 憲章が認める早期LANの内蔵・initramfsモジュール選択を尊重する。現在のbuilt-in Kconfigチェックは**今回の候補の試験契約**であり、原則的な`=y`強制に格上げしない。
- 救援SSHはP44ルートマウント失敗時・handoff後のネットワーク故障時で実行可否が異なる。`switch_root`後のsystemd障害ではUART/純正Bが現実の復旧経路で、常時救援と称さない。
- [ハードウェア設計PR #27](https://github.com/Karin-Laboratory/Debian13-Terminal6/pull/27)は別Draftであり、調査の未確認箇所やFirmware `1.00.10`／先行記録`1.01.80`の不整合も保存。検証前に一方を正しいと断定しない。
- 過去の鍵なし保存P25（private Draft Release ID 449370879 / SHA256 `353533d88ff76b22cb324ec95230ed6bf2da683026a1a227a7c5fbcecc1e9a2b`）は**この新IP変更の前のもの**。新設定・C号機個体鍵・P44通常SSHの初回公開鍵認証は未保証。
- **NO_SIGN / NO_FLASH / NO_SLOT_CHANGE / NO_REBOOT / NO_RF**。憲章・AGENTSの取り込み以外にmainを変更しない。本決定記録はDraft PR #25でレビュー。

## 次の受入ゲート

1. 公開OSS根拠をもつ`eth0/eth1`・SGMII/DSA物理ポート対応とARP実測。P25書込みなしの静的調査は先行可。実機候補試験は別承認を得る。
2. 個体専用の公開鍵／ホスト鍵を非公開工程で初回起動前に配備し、P44通常sshd（22番）とinitramfs救援Dropbear（2222番）の**独立した**認証・known_hosts・起動/停止条件を確認する。rootパスワード・空パスワードは使わない。両者の同一ポート引継ぎは要求しない。
3. 別SHAのunsigned P25 + P44対応資産を独立製造・保全し、署名・実機試験は所有者の別途承認。
4. 隔離`192.168.1.0/24`上で、**P44の最初の正常起動から**`ssh root@192.168.1.1`（22番）が公開鍵認証で成功することを確認する。別途、P44マウント失敗など承認済みの故障試験で`ssh -p 2222 root@192.168.1.1`救援経路も検証する。救援経路が未実証なら救援SSHはNOT_TESTEDのまま。
