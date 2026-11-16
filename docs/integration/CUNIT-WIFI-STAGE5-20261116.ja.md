# C号機 Wi-Fi統合 Stage 5 実行記録（2026-11-16）

## 統合

PR #13のHEAD `33102b1c5d843f3ecc89790530c7864b5ed51467` を起点に、PR #16 `75100cf183b54db9910eaec6a394c6552c81c4b5`、PR #18 `4452199fce897ef79c0ae761e5484550511873a4`、PR #17 `976bf262f28f06e1ff0c7e50d9fe2db9416ef4ba` をこの順に通常mergeした。3つとも祖先関係を保持し競合なし。mainと各担当ブランチは変更していない。

- PR #16: hwsim MLD association/recovery と仮想5/6GHz 160MHz双方向IPの分割runner。元ブランチActions `43808585110` success。
- PR #18: 独立802.11s peer、SAE/AMPEのon-wire監査、3-node supervised recovery。元ブランチActions `43808587584` success。
- PR #17: AMXRT UBus backendのopt-in stage、4 radio slot mapping、隔離2-node labのpreflight。元ブランチhost checks `43808337089` success。実1905 packet・Controller DB更新は未証明。

統合ブランチでもPR #16と#18の実通信hwsim workflowが走るよう、各workflowのpush branch条件に統合ブランチを追加した。各workflowの内部試験を緩和していない。

## 実行した検査

- `TMPDIR=/var/tmp python3 -m unittest discover -s tests -p 'test_*.py' -q`: **164件PASS**。
- `python3 -m compileall -q scripts tests packaging/easymesh`: PASS。
- tracked shellへの `bash -n`、`git diff --check`: PASS。
- 統合HEAD `aeb56b2e0dd4f2cc4e22c48090d0e030388aab0a`の[EasyMesh host checks #43811042009](https://github.com/Karin-Laboratory/Debian13-Terminal6/actions/runs/43811042009)はsuccess。
- 同HEADの[MLO hwsim #43811038087](https://github.com/Karin-Laboratory/Debian13-Terminal6/actions/runs/43811038087)はsuccess。sanitized artifactでMLD smoke 3/3、仮想5+6GHz各160MHzの双方向IPはSTA→AP 6/6、AP→STA 6/6。ただしlink別カウンタ・failoverの受入証拠はなく`acceptance_v2=NOT_PROVEN`。
- 同HEADの[802.11s hwsim #43811038073](https://github.com/Karin-Laboratory/Debian13-Terminal6/actions/runs/43811038073)は3 jobs success。2-nodeのSAE設定peer/IP、3-nodeのA↔C HWMP via Bと双方向IP、監督プロセスによるB再参加は2試行でPASS。on-wire MIC element形式は確認済み、暗号学的MICの独立検証は未実施。PCAP原本はGitHubへアップロードしていない。

## EasyMesh実通信の現在の阻害点

owner-privateのAArch64 prplMesh install treeとAmbiorix source/sysrootは見つかった。一方、実行に必要な `mod-amxb-ubus.so` と `ubusd` は当該private stageに存在せず、開発VMにはDockerもない。既存のPR #17 runnerをこのVMで実行しても、AMXRT backend/UBus preflightで停止する。従って1905実packet、Topology Query/Response、Controller DB登録/復帰は **BLOCKED**。実daemonやPCAPを得ていない状態をPASSとしない。最初の再開点は、同一AArch64 ABIのAmbiorix UBus backendとubusdをprivate stageへビルドし、隔離runnerを用意すること。

## C号機実機受入

このVMから許可されたraspi2 `codex` 接続は成功。raspi2のUSBにはRealtek 8812AUが存在するが、`wlan0`は管理経路で稼働中、`iw`も未導入。独立peerとして使用できるとの証拠はない。raspi2経由のC号機root strict SSHは `Permission denied (publickey)`。C号機の現時点の`iw phy`/radio/link stateは取得できていない。A号機は操作していない。実機RF送信・再起動・パーティション書込みは**なし**。

| 受入項目 | 状態 | 根拠/残件 |
|---|---|---|
| 3 PRの履歴付き統合 | PASS | 通常merge、競合なし |
| 164件単体テスト・構文 | PASS | ローカル実行 |
| MLO hwsim実通信 | PASS（統合HEAD） | Actions #43811038087。実機受入v2はNOT_PROVEN |
| 802.11s hwsim実通信 | PASS（統合HEAD） | Actions #43811038073。仮想3-node・2試行 |
| EasyMesh隔離1905/DB | BLOCKED | AMXRT backend/ubusd/隔離runner不足 |
| C号機802.11s peer/IP | BLOCKED | C号機root接続、独立peer不足 |
| C号機MLO 5+6GHz/IP | BLOCKED | root接続、MLO STA、radio inventory、6GHz認証ゲート不足 |

6GHz RF送信は引き続き禁止。C号機の管理経路、slot B、P25/P26/P44は変更していない。
