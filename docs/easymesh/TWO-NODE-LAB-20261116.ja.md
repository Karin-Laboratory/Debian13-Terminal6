# C号機 EasyMesh 第2段階：ARM64実行・独立2ノード実通信の試験手順

2026-11-16。対象：[PR #12](https://github.com/Karin-Laboratory/Debian13-Terminal6/pull/12)。**本書は実行手順であり、EasyMesh実通信の成功報告ではない。**

## 工程の区別

1. ARM64：既存private Debian 13 arm64成果物とsysrootでQEMU-userの動的ローダーを動かす。loader成功、実process起動、設定parse、systemd/supervisor、再起動・異常終了処理は個別に判定。423 build stepsと73 ELF検査は既存成果で、実行結果ではない。
2. Controller-Agent：**異なる2コンテナ**でprplMeshの有線1905を開始する。専用Docker internal bridgeでEtherType 0x893aをcaptureし、AL MACとTopology Query/Responseを独立照合する。
3. 無線：有線1905の成立後に2.4/5GHz NL80211、hostapd/wpa_supplicant、Multi-AP BSS、backhaul/fronthaulを組み合わせる。
4. 実機：6GHz担当から操作権が渡った後、管理LAN、SSH、route、既存AP/STAをread-onlyで採取してから段階試験する。A号機は読み取り専用。P25、regdb、driver、MLO、802.11s、6GHz RFには触れない。

## 専用ホスト

Docker、tcpdump、Docker network作成権限のある**専用Linux VM**を使い、C号機・既存管理機では実行しない。

prplMesh **6.0.1固定source commit 5ba21ee04a3b34f0d99635eeacd547d78cb67efe** を含み、start-controller-agent と start-agent が使えるrunner imageを2種類事前buildしておく。image digest、BWL、bridge/1905 transport interfaceとrunner内の設定をprivate receiptへ記録する。本スクリプトはimageをビルドせず、pullもしない。

両ノードは別AL MAC、別container/namespaceで動作する必要がある。必要なdummy WLAN、br-lan、上流platform_initの操作は**隔離コンテナ内部だけ**に限る。C号機上ではplatform_initを呼ばない。上流にも[2コンテナのController+Agent / Agent runnerの説明](https://github.com/prplfoundation/prplMesh/blob/master/tools/docker/README.md)があるが、旧リポジトリと今回の固定版の互換性は実測前提。

## 第3段階：上流Docker runnerの実バイナリ受け渡し

旧上流の公式 [Docker runner](https://github.com/prplfoundation/prplMesh/blob/master/tools/docker/run.sh) は、完成した `build/install` をコンテナへbind mountし、`INSTALL_DIR` を指定してから `start-controller-agent` / `start-agent` を起動する。runnerイメージ単体には実バイナリが含まれない構成がある。**6.0.1固定commitでこの契約を再照合し、実際のimage entrypointがbash `-c` を受け取るか確認する。** 旧GitHubミラーを6.0.1の正本と取り違えない。

Docker runnerのCPUアーキテクチャと、利用する実バイナリのELFアーキテクチャを**一致**させる。一般的なx86_64ラボ用にはprplMesh 6.0.1のネイティブx86_64ビルドが必要で、既存AArch64 cross-buildをx86_64イメージへ直接マウントしても動かない。arm64イメージを使う場合はarm64 Docker実行環境または明示的なQEMU/binfmt設定が必要。スクリプトは `readelf` とDocker imageのarchitectureを照合し、不一致なら起動前に拒否する。

既存のprivate成果物の `build/install`（`bin/beerocks_agent`、`bin/beerocks_controller`、`scripts/prplmesh_utils.sh` を含む）を入力に、隔離ホストで次を実行する。runnerは元のinstall treeをコンテナに直接マウントせず、private output以下へController用・Agent用の**別々のコピー**を作り、その各コピーをマウントする。上流起動スクリプトに必要な `INSTALL_DIR` を設定し、各コンテナ内の `br-lan` に固定AL MACを付与した後にサービスを起動する。Agent再起動にも同じAL MACを適用する。これらの変更はコンテナ内だけで行い、C号機やホスト管理LANには触れない。

~~~sh
python3 packaging/easymesh/run-easymesh-two-node-lab.py \
  --controller-image <local-prplmesh-6.0.1-runner-image> \
  --agent-image <local-prplmesh-6.0.1-runner-image> \
  --install-tree <private-prplmesh-build-install> \
  --install-target <compiled-CMAKE_INSTALL_PREFIX> \
  --controller-al <private-controller-AL-MAC> \
  --agent-al <private-agent-AL-MAC> \
  --controller-db-command 'beerocks_cli -c bml_conn_map' \
  --output <new-private-directory> --duration 60 --outage 45 --execute
~~~

- `--install-target` はコンテナ内のmount先と `INSTALL_DIR`。既存cross buildで `CMAKE_INSTALL_PREFIX` に絶対パスを埋め込んでいる場合は**その元の値を渡す**。未指定の既定値 `/opt/t6-prplmesh` は相対パス前提で再現できるイメージ用。個別イメージの必要パスは実起動で確認する。
- `--install-tree` 省略時は実バイナリをすでに含む独自のprebuilt image向け従来動作のまま。イメージ単体に必要な実バイナリが存在するか確認すること。
- `--auto-al` はコンテナ起動後に `br-lan` MACを読み取る調査用モード。Agent再作成後のMAC不一致を復旧成功と扱わず停止するため、**完全な復旧実証には固定の明示AL MACを使う**。
- 参照イメージのtagではなく、実image digest・ソースcommit・設定・実プロセス・実PCAPをprivate記録に残す。合成テストや単なるdaemon PIDだけでは合格としない。
- upstreamの `platform_init` やネットワーク再構成が必要なときも、許すのはこの隔離ラボ内だけ。ホスト・C号機での実行は禁止。

現セッションで実行可能な環境にはDocker、tcpdump、QEMU-user、private ARM64 sysrootがないため、**本変更は起動契約の修正であり、実プロセス成功や実1905通信成功を示すものではない**。次に実ラボで上記コマンドを実行し、private出力に保存される起動時Dockerログ、3つの実PCAP、Controller DBスナップショットを検証する。失敗時は `failure.json` を保存する。

## ARM64の第1ゲート

~~~sh
python3 packaging/easymesh/verify-arm64-linker.py \
  --stage <private-AArch64-install-prefix> \
  --sysroot <private-Debian13-arm64-sysroot> --qemu qemu-aarch64
~~~

Loaderだけの結果を実プロセス起動のPASSにしない。起動試験は別の隔離ARM64 VM/hostで、ieee1905_transport、beerocks_controller、beerocks_agent、beerocks_vendor_messageそれぞれの実起動、設定parse、停止・cleanup、supervisor・systemdを測る。

## 実2ノードの第2ゲート（明示opt-inのみ）

~~~sh
python3 packaging/easymesh/run-easymesh-two-node-lab.py \
  --controller-image <prebuilt-prplmesh-6.0.1-controller-runner> \
  --agent-image <prebuilt-prplmesh-6.0.1-agent-runner> \
  --controller-al <private-controller-AL-MAC> \
  --agent-al <private-agent-AL-MAC> \
  --output <new-private-directory> --duration 60 --outage 45 --execute
~~~

ControllerデータベースのAgent登録・喪失・再登録も検証したい場合は、対応するcontroller image内の取得コマンドを次のように渡す。CLIの実行ファイル・構文・出力が利用できることを事前に確認し、プライベートな実MACは公開しない。

~~~sh
# 例：イメージにbeerocks_cliが実在し、map出力にAL MACが含まれる場合
--controller-db-command 'beerocks_cli -c bml_conn_map'
~~~

この指定がない場合、PCAPからwire topologyの復帰は確認できても、**Controller DBとAgent喪失検出の合格判定は必ずfalse**となる。指定した場合は初回・Agent停止後・復帰後の3スナップショットを比較し、初回と復帰後にAgent AL MACが存在し、停止後には存在しないことを要求する。CLIが応答しない・AL MACが見つからない場合も未合格とする。

本runnerはDocker内専用internal bridge、Controller+Agentコンテナと独立Agentコンテナを使う。**capture開始後に各プロセスを起動**し、Agent停止→停止中capture→Agent再起動前にcapture開始→復帰後topologyを再検証。--executeなしでは何も作らない。--privilegedは使用せず、NET_RAW/NET_ADMINをコンテナ内部のみに付与する。終了時は自分が作った2コンテナとネットワークのみ削除し、既存のDocker環境・ホスト管理IFを変更しない。

3つの生PCAPとverdict.jsonは新規0700プライベートディレクトリへ保存する。生PCAP、MACを含むログ、秘密、認証情報はGitHubに公開しない。

PCAPだけを検証する場合：

~~~sh
python3 packaging/easymesh/verify-ieee1905-pcap.py \
  --pcap <private-capture.pcap> \
  --controller-al <private-controller-AL-MAC> \
  --agent-al <private-agent-AL-MAC>
~~~

Classic Ethernet PCAP（VLAN可、pcapng不可）に対して、双方のAL MAC TLVつきTopology Discovery (0x0000)、Controller→AgentのTopology Query (0x0002)、AgentからDevice Information TLVを持つTopology Response (0x0003)と**Message ID一致**を検証する。破損、非完了fragment、MID不一致はPASSにしない。

## 受入証拠の区分

| 成功条件 | 個別証拠 |
|---|---|
| 実ARM64起動 | 別のtarget実プロセスと終了コード、設定parseログ、QEMU/ABI区分 |
| 独立2ノード | 2コンテナの別PID/namespace、Controller+Agent/Agentの実プロセス |
| 1905 wire discovery/topology | 実PCAP、両AL MAC、Query/Response MID一致 |
| Controller DB更新 | Controller CLI/API/DBの登録スナップショット |
| Agent喪失・復帰 | Agent停止後のController DB喪失検出、再登録、時間とログ |
| backhaul/fronthaul | 独立peerリンク、Multi-AP BSS、端末associationと双方向IP |
| C号機復帰 | read-only preflight、管理LAN/SSH/route、再起動後の復旧 |

**Wireの往復成功だけではController DB更新と喪失検出をPASSとしない。** Agent停止中にフレームがないだけでも喪失検出の証明ではない。合成PCAPは検証器の単体テストであり、実1905の成功ではない。

## 2026-11-16 agent-101-vm runtime試行結果

- private ARM64 prplMesh 6.0.1 install tree、Debian arm64 rootfs、同ビルドが使ったprivate AMX target librariesを隔離stageへ集め、`verify-arm64-linker.py`で4 executableのtarget loader dependency解決を確認した。QEMU-userで`ieee1905_transport`単独を起動し、SIGTERMによる終了も確認した。単独transportはTopology往復を意味しない。
- 独立した一時netns/veth/bridgeで2-node runtimeを試したが、ControllerがAMXRT `No backends specified`で起動できず、Agentは未定義radio interface mappingによりretry、transportは`eth1`/`br-lan`をuntrackedとして扱った。PCAPはglobal headerのみで、Discovery/Query/Responseなし。verdictはFAILであり、EasyMesh通信PASSにしない。
- 試験に使ったnetns/bridge/processはすべて削除した。次回はAMXRT backend/plugin/configの不足を満たし、`wireless_interface_0/1`などPR #12のplatform DB mappingとtest-only radio interfacesを構成して、再び隔離2-node captureを行う。C号機やraspi4上でこのQEMU実験は実施しない。

## この作業セッションの結果

- 既存private ARM64 ELFとtarget sysrootはこの実行環境に存在せず、QEMU-userもないため**ARM64実行はNOT RUN**。
- Docker/tcpdumpが利用できずCAP_NET_ADMIN権限もない。network namespaceとveth作成は拒否されたため、**独立2ノード・PCAP実測・障害復旧はNOT RUN**。
- IEEE1905 PCAP検証器とDocker internal-network 2ノードrunner、合成回帰テストを追加した。これらを実prplMesh成功として計上しない。
