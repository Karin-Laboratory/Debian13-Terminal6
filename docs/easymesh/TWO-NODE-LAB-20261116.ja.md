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

## この作業セッションの結果

- 既存private ARM64 ELFとtarget sysrootはこの実行環境に存在せず、QEMU-userもないため**ARM64実行はNOT RUN**。
- Docker/tcpdumpが利用できずCAP_NET_ADMIN権限もない。network namespaceとveth作成は拒否されたため、**独立2ノード・PCAP実測・障害復旧はNOT RUN**。
- IEEE1905 PCAP検証器とDocker internal-network 2ノードrunner、合成回帰テストを追加した。これらを実prplMesh成功として計上しない。
