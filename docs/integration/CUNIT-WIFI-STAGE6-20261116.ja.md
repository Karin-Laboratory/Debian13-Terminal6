# C号機Wi-Fi統合 Stage 6：実通信ゲートの実装・試験記録

更新: 2026-11-16 JST / 統合 Draft PR #13 / 起点 `0dbfd3a548bea22088f8022b8beb3a5d03c83666`

本記録は新規実測と既存実測を区別する。PR #13はDraftでmain未マージ。A号機、C号機、raspi4の設定・eMMC・slot・RFを変更していない。Stage 5の[受入原本](CUNIT-WIFI-STAGE5-20261116.ja.md)を引き継ぐ。

## 1. 変更・証拠・判定

| ゲート | Stage 6の新規実装・観測 | 判定 |
|---|---|---|
| Debian13 AArch64 UBus OSSの再現ビルド | OpenWrt公式libubox `a396f38a8568a1d670c240465cd8d24fdfdf6463` とubus `db20eff5535fe3126c05dc0edc029caf0e82fe10`を固定し、Debian trixie/arm64でソースからbuild。libubox/libubus/libblobmsg_json/ubusd/ubusのAArch64 ELF検査と、ビルドしたubusd↔ubusの実Unix socket IPCを確認 | **PASS** [Actions #43877480749](https://github.com/Karin-Laboratory/Debian13-Terminal6/actions/runs/43877480749) |
| UBus runtimeのprplMesh Labへの引継ぎ | 匿名レシートのos/arch/実IPC結果/ファイルSHA256を照合してから、ControllerとAgentの独立したprivate stagingへubusd/ubus/公開libをコピー。既存prplMeshファイル上書きを禁止。host回帰試験はPASS | **PASS（コード・host tests）、実2ノード起動は未証明** |
| Ambiorix `mod-amxb-ubus.so` | 既知private checkout commit `c74118306cd9f4557de2a8963c21f6d4a94c6f89` とnative Debian13/AArch64 AMX core、上記UBus stageでビルドする実行スクリプトを追加。ELF不一致は拒否。privateソース/libを公開しない | **NOT_TESTED**（当実行環境にprivate prefix/checkoutがない） |
| AMXRT Controller/Agent起動・1905 | backendロード、実process、0x893a Discovery/Query/Response MID、Controller DB登録→喪失→再登録を実観測する必要がある | **BLOCKED**（pluginを含むprivate full runtimeと独立2-node実行環境が未成立） |
| raspi4→C号機の正規SSH | 既存strict鍵、known_hostsを維持して経由試験し、成功時にradio・kernel・regdbをreadonly記録する診断スクリプト追加。今セッションでは実ネットワーク接続不可 | **NOT_TESTED**（過去raspi2→Cはpublickey FAIL） |
| 802.11s実機peer | 管理中のraspi2 Realtek 8812AUを流用せず、独立mac80211/nl80211 2.4GHz mesh-point対応PHY・wpa_supplicant SAE/AMPE・法令上の条件確認が必要 | **BLOCKED**（独立peerと正規C接続が未確認） |
| MLO実機Acceptance v2 | Stage 5のhwsim 5/6GHz 160MHz/双方向IP PASSは保持。実機のMLD、別radio ID、リンク別TX/RX、両リンク障害復帰、継続IPは未測定。6GHz RFは送信禁止を維持 | **BLOCKED**（正規接続・MLD peer・6GHz認証/regdbが未充足） |

## 2. 新規ソースと実行手順

[固定ソースUBusネイティブビルド](../../packaging/easymesh/build-debian13-arm64-ubus-stack.sh)：**専用のDebian 13 arm64実行環境**で実行する。別OS・別アーキテクチャは先に拒否する。デバイス・ホストネットワークは変更せず、新規private stageへだけ配置。GitHub CIが配布するのは匿名receiptのみなので、private VMではこのレシピを再実行する。

```sh
bash packaging/easymesh/build-debian13-arm64-ubus-stack.sh \
  /private/new-debian13-arm64-ubus-stage
# 成果物：.../install/lib/libubus.so, libubox.so, .../sbin/ubusd
# .../receipt.json 実IPC PASSを独立照合
```

[Ambiorix backendネイティブbuildゲート](../../packaging/easymesh/build-amxb-ubus-debian13-arm64.sh)：Stage 5で所有者のprivate領域に保存された公式source checkoutと同一ABIのAMX libsを渡す。**このスクリプトのbuild成功は今回未実測**。既存privateソースをコピーした一時領域で `make` し、実AArch64モジュールをprivate stageへ取り出す。ビルド手法の依存関係が合わなければ初回のmakeエラーを保存し、上流Makefileに合わせて修正する。

```sh
bash packaging/easymesh/build-amxb-ubus-debian13-arm64.sh \
  <private-official-amxb_ubus-checkout> \
  <private-AArch64-Ambiorix-core-prefix> \
  /private/new-debian13-arm64-ubus-stage/install \
  /private/new-backend-output
```

[既存独立2-node Lab runner](../../packaging/easymesh/run-easymesh-two-node-lab.py)に `--ubus-stage` を追加。レシートを照合し、Controller/Agent双方でprivate DB、AL MAC、専用UBusを独立起動する。上流の `start-controller-agent`/`start-agent` は維持し、1905パケット生成の独自実装はしない。

```sh
python3 packaging/easymesh/run-easymesh-two-node-lab.py \
  --controller-image <native-arm64-debian13-image> \
  --agent-image <native-arm64-debian13-image> \
  --install-tree <private-prplmesh-6.0.1-install-with-backend> \
  --install-target <compiled-CMAKE_INSTALL_PREFIX> \
  --ubus-stage /private/new-debian13-arm64-ubus-stage/install \
  --amx-ubus \
  --controller-platform-db <private-0600-controller-db> \
  --agent-platform-db <private-0600-agent-db> \
  --controller-al <private-controller-AL-MAC> --agent-al <private-agent-AL-MAC> \
  --controller-db-command 'beerocks_cli -c bml_conn_map' \
  --output <new-private-lab-dir> --duration 60 --outage 60 --execute
```

**要確認：** 上記backend作成scriptの出力は、そのままprplMesh install treeとは限らない。runnerが参照する `lib/amxb/mod-amxb-ubus.so` と必要libsを、privateなprebuilt prplMesh install treeへ**非破壊的にstage**してから起動する。全てのバイナリは同一arch/ABIとし、`LD_LIBRARY_PATH`とcompiled backend pathの有効性は実起動ログで判定する。

## 3. 正規管理SSHの復旧検査

[読み取り専用SSH検査](../../scripts/cunit_management_ssh_probe.py)は、raspi4管理用の**既存**アカウントとgateway側の**既存**target identityを受け取る。ユーザ/鍵/host keyの生成、authorized_keys編集、再起動、slot切替は行わない。生ログは新規private outputに0600で保存し、公開の結果は成功/失敗種別のみ。

```sh
python3 scripts/cunit_management_ssh_probe.py \
  --gateway <existing-user@raspi4-alias> \
  --target root@192.168.3.1 \
  --existing-target-identity-on-gateway <absolute-existing-key-path-on-raspi4> \
  --private-output <new-private-ssh-receipt-dir>
```

分類の順番：gateway接続→raspi4側target keyの存在・known_hosts認証→C号機側publickey accept→readonly inventory。認証が拒否されれば対象鍵の一致、SSHログ、authorized_keysの差異を**権限内の別経路**で比較する。原因が不明なまま認証変更・鍵製造はしない。今セッションからの家庭内raspi4経路は使用できないため**新しい実SSH成功は未観測**。

## 4. 802.11s実機peer要件

既存raspi2の`wlan0`（Realtek 8812AU, `rtw88_8812au`）は管理系としてUP。独立mesh peerの対応は未実証で、転用不可。必要な追加・既存機材の選定条件は以下。

1. Linux upstream mac80211/nl80211対応、`iw phy`で`mesh point`を広告する**管理と独立のPHY**（単なる「802.11s対応」という製品名では不十分）。
2. 2.4GHzで使用予定チャネルが規制上許容され、peer双方のdriver/firmwareがSAE/AMPEに対応。wpa_supplicantによる`mode=5`と実peer確立を検証可能。
3. 別USBポートまたは独立ホスト/namespace、管理LANを切断せずに試験可能な構成。既存wlan0の切断・bridge変更を行わない。

この条件を満たすpeerが得られるまではC号機のmesh通信を実施しない。過去の802.11s hwsim実通信は[Stage 5](CUNIT-WIFI-STAGE5-20261116.ja.md)のPASSを引き継ぐ。

## 5. MLOの実機Acceptance v2へ進むためのread-onlyゲート

[Acceptance v2](../wifi7/CUNIT-MLO-EVIDENCE-V2-20261116.ja.md)に必要なのは、`iw phy`等で得たradio inventoryだけではない。AP/STAの同一MLD、異なるlink ID/radio ID、5/6GHz各160MHzの実リンク、リンク別TX/RX前後値、順次片リンクdown/up、各段階双方向IP、最後の再関連付けが必要。まず管理SSHが成立しても**無線送信なしのinventory**だけを実施し、適法な6GHz条件・trusted regdb・対応対向STAがない限りRF試験へ進まない。既存hwsim PASSをhardware PASSへ繰り上げない。

## 6. 既存PASSと残工程

- 既存Stage 5の**164単体テスト、MLO hwsim、802.11s hwsim**の実績を再実行目的で上書きしない。今回の変更箇所のみ回帰試験を追加する。
- 今回の公開OSS UBusビルド [Actions #43877480749](https://github.com/Karin-Laboratory/Debian13-Terminal6/actions/runs/43877480749)：新しいactual-ubusd↔ubus IPCを実証。これは実1905とは別のプロトコル/受入ゲート。
- 今回のhost regression [Actions #43877899942](https://github.com/Karin-Laboratory/Debian13-Terminal6/actions/runs/43877899942)：**168件PASS**、後続コミットについては別のrunを参照する。
- 次の最優先実作業はnative backend `mod-amxb-ubus.so` のprivateビルド→動的ロード→隔離2-nodeで1905 PCAP→Controller DB→Agent再接続。外部制約で停止したら、raspi4 SSH正規ルート確認と独立2.4GHz peer準備へ進める。
