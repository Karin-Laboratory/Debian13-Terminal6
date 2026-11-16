# C号機 Debian 13 / Wi-Fi統合 Codexランブック

更新基準: 2026-11-16 JST。対象: `Karin-Laboratory/Debian13-Terminal6`、統合PR #13、C号機（Debian 13 / Linux 6.18.63）。**この文書は作業の入口であり、最新の実機事実を自動保証するものではない。** 各実行でPR/Actions/機器状態の差分だけ確認し、ここに記録済みの調査を漫然と繰り返さない。

## 0. 開始時の最短手順（毎セッション）

1. `git status --short --branch`、`git log -5 --oneline`、PR #13および依存PR #6（6GHz/regdb/no-320）、#9（EEPROM/OTP）、#10（MLO）、#11（802.11s）、#12（EasyMesh）の**最新HEAD、更新日時、CI結果**を読む。非公開署名は `SBAT6A-Offline-Archive` PR #159の権限内でのみ照合する。古い本文・候補SHAを現行とみなさない。
2. [統合実測の原本](CUNIT-WIFI-INTEGRATION-20261116.ja.md) の最新節と、本書「現時点の引継ぎ」を照合。前回からの**変更点のみ**を列挙する。PR説明と実測ログが矛盾するときは日時・個体・イメージSHAを使い個別に解決し、古い記述を上書きしてごまかさない。
3. 必要な対象に限り、接続経路（raspi4→C号機）、現行slot、`boot_a`のサイズ/SHA、100MHz/no-CQE、P44、Ethernet/SSH、`iw phy`、regdbの**読み取り専用スナップショット**を取得する。通信できないときは接続障害として報告し、以前の実測を今回の結果に流用しない。
4. **既にPASSした工程は、入力・条件・SHAが変わらない限り再実施せず証拠を参照**する。次の未達ゲートを一つ選び、OSS既存実装の統合・移植・検証を優先する。別担当のPR、実機、ブランチを勝手に書き換えない。
5. 作業後は「変更→証拠→PASS/FAIL/BLOCKED/NOT_TESTED→次の一手」を同一PRの記録へ追記。機密ログはprivate領域に限定する。

## 1. 引継ぎ状態（記録時点）

| 対象 | 最後に裏付けられた状態 | 次のゲート |
|---|---|---|
| PR #13 | 5 PRの祖先関係を保持して統合、host CI PASS、unittest 138件PASS（当初137件、追記後138件）。main未マージ、Draft | 新P25の保管・書込み・実機受入 |
| kernel source | 正規6.18.63 tarball→private snapshotの**全ファイル再生一致**を達成（`.gitignore`除外88ファイル問題を修正）。private差分の来歴分離、公開再現性、ライセンス適合までは証明していない | 変更後再生receiptを保持 |
| ARM64 | `CONFIG_MAC80211_MESH=y`、`CONFIG_MT7996E=m`、署名regdb必須、160MHz/no-320のImageとmt76系moduleビルドPASS | **実機適用は別判定** |
| 統合unsigned P25 | 32MiB、SHA256 `83478d8804172777c9dc69fd35a1e3931257a130a5c803e588b6e286c390cd2e`、DTB 100MHz/no-CQE、wens署名DB、構造検証PASS | 署名済みイメージの厳密な一致と保管 |
| 保護署名 | 添付Codexログ末尾ではPR #159経由で署名/RSA-PSS独立検証PASS、signed SHAは `ae65d0c2…46dea0`。**完全SHAはprivate receiptから再取得すること** | Actions artifact容量上限による保存失敗を、既存出力の再照合→private Draft Release保存で解消。成功の再確認までは「保管済み」にしない |
| C号機の現行起動 | 最終確認はslot A、既存signed `boot_a` SHA `8457ae5b31d38a754442ed0826544e19cf262059d8578b1eb0218d1cc3f2beb8`。eMMC HS400・約95MHz・CQE無効、管理LAN/SSH、P44 RW | 署名済み**統合**P25は未適用。適用前に現行を再測定 |
| 2.4/5GHz | 過去のSTA+WPA2+DHCP+IP/TLS PASS。統合PRの新環境では対向機・userspace不足で未再試験 | 既存成功を保持、必要なら差分試験 |
| 6GHz | no-320/160MHz能力広告は実機PASS、RFは未送信。現行regdb署名不一致、global `00`、6GHz disabled | trusted regdbの起動読込確認。**技適の個体照合・運用条件を別に確認するまで送信禁止** |
| 802.11s | 3 VM hwsim A↔C/IPとassisted rejoin PASS。automatic recovery FAIL、AMPE保護は未証明。現行C号機kernelではmesh無効 | 統合kernel起動後にMESH_POINT確認→peer実通信 |
| MLO | 判定器28 tests PASS、実MLD二リンク受入は未達。hwsim実行で失敗/中止記録あり | AP/STA同一MLD、異なる2 radio、リンク別送受信・断復帰の実測 |
| EasyMesh | prplMesh 6.0.1 ARM64 build/ELF/host checks PASS、実機process/socketなし | Controller・Agentと実IEEE 1905の2ノード通信 |

**注意**：PR本文や一部時系列ドキュメントには「P25未署名」など**過去の時点**の文章がある。判断は候補SHA・計測日・実行IDで行う。「signed」は「Release保管済み」「実機書込み済み」「起動成功」「RF送信許可」と同義ではない。

## 2. 判定ゲート（順番を飛ばさない）

### G0: 接続と復旧の確認（書込み前）

- raspi4直結の管理LAN/SSH/UARTが実際に利用できること、C号機のslot/PARTNAMEを読み取って照合。DHCPが使える前提で家庭LANを探し回らない。
- 対象C号機のstock slot Bへの切替・復帰は過去に成功記録あり。ただし**今回の書込みサイクルでstock Bが起動するか**は必要に応じ再検証。電源サイクルが必要なら人間へ明示して停止する。
- `boot_b`、P26、P44 raw、GPT、misc、EEPROM/OTP/OEM・校正領域を巻き込まない。パーティション番号ではなく`PARTNAME`、容量、現行SHAで最終同定する。privateバックアップと復旧手順の場所を先に確認。

### G1: 入力の独立検証（ホスト）

- 正規tarball・private snapshot・追跡漏れ（ignore対象を含む）の全量inventory照合、差分適用、`olddefconfig`、Image/moduleビルド、receiptを**それぞれ別結果**として保存。
- `CONFIG_MAC80211_MESH=y`、`CONFIG_MT7996E=m`、`CONFIG_CFG80211_REQUIRE_SIGNED_REGDB=y`、100MHz/no-CQE DTB、160MHz/no-320を検査。
- 過去の**不採用P25**: DTBに200MHz / `supports-cqe`が残っていた。新候補に再混入させない。
- `regulatory.db`本体と`.p7s`の組合せ、署名者がkernel内の信頼鍵に含まれるかを検証。以前のDebian署名者 `benh@debian.org` はこのkernelでは不一致、upstream `wens`署名を検証済み。単にCMS検証PASSだけで実機ロードPASSにしない。

### G2: 署名・保存（privateのみ）

- unsigned 32MiB P25、DTB、initramfs、workflowのcheckout pin、exact-SHA許可、one-shot marker、共有lock、署名後のbody不変、独立RSA-PSS/証明書チェーンを照合。**候補SHAが変わったら旧署名を絶対に流用しない。**
- 署名ジョブがcheckout pin不一致で停止した前例あり。署名前に固定commitが現行の署名スクリプトを含むか検証する。
- **今回の既知障害**: GitHub Actions artifact容量上限でアップロードに失敗。署名・RSA-PSS検証はPASS。まず同じ保護環境の**既存の検証済み出力が残るか**を確かめ、exact signed SHAを再計算してprivate Draft Releaseに保存し、Release assetを読み戻してSHA一致を確認。存在しない場合にだけ、one-shot条件と権限を見直して再製造を判断する。失敗した保存処理を理由に無条件で再署名しない。
- 公開リポジトリへ鍵・privateソース・firmware dump・認証情報・個体識別ログを出さない。

### G3: 実機boot_a適用（復旧が成立する場合のみ）

- 管理接続、現行slot、stock B復旧、`boot_a`のPARTNAME/32MiB/未mount、元の全量バックアップSHA、署名済み候補**完全SHA**と証明receiptを先に確認。
- 書込みは`boot_a`のみに限定。過去にSSHパイプ経由BusyBox `dd`の短いreadで**約808KiBしか書かれなかった**障害あり。再開時は実行環境の`dd`機能を調べ、`iflag=fullblock`または同等の確実な全量読込を使用する。**全32MiB readbackとSHA一致前は絶対にslot Aへ切り替えない。**
- readback後に必要なslot切替・再起動を行い、Linux起動、管理Ethernet/SSH、P44 RW、UART復旧経路を確認。接続不良時に「起動成功」「復旧失敗」を推測で断定しない。OS起動証拠が得られない場合は中止し、ユーザーの物理操作を待つ。
- 実機の`boot_a` SHAを再取得し、artifact / receipt / readbackの3者一致を記録。

### G4: 新kernelの読み取り受入（RF送信なし）

- `uname -a`、`/proc/config.gz`、`iw phy`のinterface modes、160MHz広告・320MHz非広告、regdbの起動ログ・`iw reg get`・channel flags、module SHAとサービス復帰、eMMC 100MHz/no-CQE・MMC/ext4 error、Ethernet/SSHを確認。
- `CONFIG_MAC80211_MESH=y`というhost configだけでは不十分。現行機は`mesh point`がなく、IF追加が `Operation not supported (-95)`で失敗した。新kernelで実際に登録されるまでPASSにしない。
- regdb信頼鍵が一致しても、実機起動時読込と使用可能チャネルを観測すること。**ここまでの成功で6GHz送信を始めない。**

### G5: 機能別実通信（独立ゲート）

- 2.4/5GHz: 相手機器、認証、DHCP/IP、ping/TLS、再起動後の記録。過去成功と今回成功を区別する。
- 6GHz 160MHz: C号機の型式/技適番号・個別認証条件、改造構成の周波数/電力/アンテナ/屋内外条件を確認し、適法な送信が立証された場合のみ、AP beacon→WPA3-SAE/PMF→IP→実160MHz/EHT→再起動を測定。通常運用は320MHz非広告・非使用。320MHz電波暗室モードは**方針のみ・未実装**、SSH指定だけでRF解禁とはしない。
- 802.11s: hwsim assisted recoveryとautomatic recovery/AMPE/実C号機を別判定。独立peerを使ってSAE/AMPE、HWMP multi-hop、切断再収束、双方向IPを確認。
- MLO: [受入証拠v2](../wifi7/CUNIT-MLO-EVIDENCE-V2-20261116.ja.md)を使用。**単一MLDの2リンク**、異なるradio ID、5/6GHz各160MHz、リンク別TX/RX増加、両リンク順次切断/復帰、IP継続がなければPASSにしない。2つの独立STA接続は代用不可。
- EasyMesh: prplMesh Controller/Agent、IEEE1905 Discovery/Topology、切断・再接続を実process/packetで観測。ビルド/ELF監査と実通信を混ぜない。

## 3. 既知の失敗 → 次回の最短対処

| 症状 | 既知原因/留意点 | 先に行うこと |
|---|---|---|
| 署名workflowが前段で停止 | checkout commit pinが旧スクリプトを指す | pinとスクリプトを照合、署名関数実行・one-shot markerの有無を確認 |
| 署名PASSなのにjobが赤 | artifact保存容量上限 | 独立検証済み出力を確認しprivate Release保管を再試行。署名を繰り返さない |
| 6GHzがglobal `00` / disabled | regdb `.p7s`署名者がkernel鍵と不一致 | signer/key/DB payloadと起動ログを比較、regdbを不正にバイパスしない |
| Meshが`-95` | 現行kernelの`CONFIG_MAC80211_MESH`が無効 | host configでなく**起動したkernel**のconfigとinterface modesを見る |
| source replay不一致 | `.gitignore`に一致する88ファイルが差分生成から漏れた | ignored sourceを含むinventoryで再実施 |
| no-320パッチがそのまま当たらない | 統合snapshotとhunk文脈が違う | 対象を一意照合して意味的に適用後、再び全ファイル独立再生 |
| Wi-Fi testできない | peerやhostapd/wpa_supplicant/prplMesh実行環境不足 | コード欠陥と誤判定せず必要機材/パッケージを報告 |
| raspi4/C号機SSH失敗 | 実行環境の経路/権限/リンク差 | 直結経路と実機状態を確認。無断の管理設定変更や推測による復旧操作を避ける |
| `dd`書込みサイズ不足 | SSHパイプ短read | 全量読込を保証してから再試行し、readback SHA一致まで切替禁止 |
| slot B切替後pingのみ応答 | SSH refused、UART採取空の記録あり | その回のstock OS起動は未証明。物理電源サイクル・slot再確認まで停止 |

## 4. Codex報告テンプレート

```text
日時(JST) / repo / branch / PR / HEAD / Actions run:
前回から変わった点:
今回の対象ゲート (G0〜G5):
実施操作（read-only / host build / device write / RF を明示）:
PASS（証拠、SHA、run URL、実測時刻）:
FAIL（最初に失敗した工程とログ）:
BLOCKED（外部依存と解除条件）:
NOT_TESTED（未実施を成功に含めない）:
現在のC号機slot・boot_a SHA・100MHz/no-CQE・管理経路:
RF送信の有無 / 技適・regdb判定:
private原本の保存先（公開可能な抽象名のみ）:
次の一手（重複作業なし）:
```

## 5. 原本と参照先

- [統合PR #13](https://github.com/Karin-Laboratory/Debian13-Terminal6/pull/13) と[統合ログ](CUNIT-WIFI-INTEGRATION-20261116.ja.md)
- [6GHz認証・regdb・過去P25の失敗](../wifi/CUNIT-6GHZ-CERTIFICATION-REGDB-GATE-20261115.ja.md)
- [160MHz/no-320 host候補](../wifi/CUNIT-6GHZ-160MHZ-HOST-CANDIDATE-20261115.ja.md)
- [MLO証拠契約](../wifi7/CUNIT-MLO-EVIDENCE-V2-20261116.ja.md)
- [非公開署名PR #159（権限保持者のみ）](https://github.com/Karin-Laboratory/SBAT6A-Offline-Archive/pull/159)
- [既存stock UART・P43/P44事前条件](../COMMON-STOCK-UART-P43P44-ENTRY.ja.md)

**改訂ルール**: 事実が更新されたら過去の成功/失敗を消さず、日時・イメージSHA・試験対象を明記して「現時点の引継ぎ」と失敗表を更新する。継続開発の開始指示は「このランブックのG0から差分確認し、最初の未達ゲートだけ進める」で足りる。
