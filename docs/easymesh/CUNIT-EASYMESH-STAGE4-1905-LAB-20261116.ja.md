# C号機 EasyMesh 第4段階：実1905交換の再試験準備

2026-11-16 / 専用 Draft PR #17 / 統合 Draft PR #13 を基点とする独立ブランチ。

**判定原則**：上流の実prplMesh 6.0.1をController/Agent別々のネットワーク名前空間で実行し、実PCAPからIEEE 1905.1の送受信とTopology復帰を確認する。単体テスト・ELFローダー・daemonのPID・合成PCAP・空の24 byte PCAPはいずれも**実通信PASSではない**。

## 前回の実測と今回の修正

- 前回、独立 QEMU-user/ARM64 2-node試行は **FAIL**：Controllerが `AMXRT No backends specified`、Agentがradio index 2/3のmapping不在、transportが `eth1/br-lan` をuntracked扱い、PCAPは24-byte headerのみで1905の実パケット0件。試験環境は破棄済み。C号機・A号機・raspi4を変更していない。
- 上流 prplMesh 6.0.1の基準入力として `5ba21ee04a3b34f0d99635eeacd547d78cb67efe` を維持。上流正本は[GitLab](https://gitlab.com/prpl-foundation/prplmesh/prplMesh)であり、古い GitHub archive は**6.0.1の正本ではない**。固定コミットの適合性は実際のcheckoutで `git rev-parse HEAD` を確認する。ローカルLinux BPLパッチの来歴・licenseは [既存patch README](../../patches/prplmesh/README.md) を参照する。
- **AMXRT**：共有ライブラリ `libamxb.so` だけでは `No backends specified` を解消できない。Ambiorix `mod-amxb-ubus.so` と有効な `ubusd` socketを別途用意する。上流 prplOS feed で使用する `AMBIORIX_BACKEND_PATH` と `AMBIORIX_BUS_URI` のCMake指定を、`PRPLMESH_AMX_LAB_UBUS=1` の専用ビルドへ追加。プラグインを private install stage の `lib/amxb/` へコピーする。**現時点ではbackendの実ロード成功は未実証**。
- **Agent mapping**：既存 Linux BPLパッチのradio index上限を0/1→0/3へ拡大。設定の無いindexは従来どおり失敗する。private node configに `radio_ifaces_extra=lab2,lab3` があるときだけ `wireless_interface_2/3` をrendererが追加。重複・不正interface名を拒否する。これらは試験用radio名のmappingであり、独立無線radioの成立証拠ではない。
- **transport**：隔離ラボの実Docker `eth0` をprivate `br-lan` へattachし、Controller/Agentの独立 `br-lan` に別々のAL MACを設定。private `prplmesh_platform_db` で `backhaul_wire_iface=eth0` を明示し、1ノードずつ `/tmp/beerocks/prplmesh_platform_db` に配置。C号機やホストのinterfaceには触れない。
- **recovery**：Agent再作成時に、初回起動と同じ `install_target`、AMXRT、UBus、AL MAC、独立private DBを再適用する。既存Runnerの再起動時にinstall prefixが既定値へ戻る問題を解消。
- [既存2-node捕捉/受入runner](../../packaging/easymesh/run-easymesh-two-node-lab.py)、[1905 PCAP検証器](../../packaging/easymesh/verify-ieee1905-pcap.py)は継続利用し、新規の1905独自プロトコルは実装しない。

## 実行前の必要物

1. 既存の上流6.0.1ソース、対応するhostapd 2.12/include、Ambiorixライブラリと **`mod-amxb-ubus.so`** が含まれるprivate target prefix、AMXホストコードジェネレータ、libubus/libuboxなどtarget backend依存。実バイナリのarch、backendのloader依存、license、source/commitを非公開レシートに記録。
2. Docker、tcpdump、NET_RAW/NET_ADMINを**自分が作った隔離コンテナにのみ**付与できる専用Linux VM。runnerイメージには `ubusd` と `ip` が必要。実行するELFとimageのCPU architectureを一致させる。外部ネットワークは実験用internal bridgeから利用しない。
3. `install-tree` は`bin/beerocks_controller`、`bin/beerocks_agent`、`bin/ieee1905_transport`、`scripts/prplmesh_utils.sh`、`lib/amxb/mod-amxb-ubus.so` が存在する実stage。CMakeが埋め込んだinstall prefixを `--install-target` に指定する。
4. Controller用とAgent用で**別個の**root/caller-owned mode 0600 platform DB。両方に `backhaul_wire_iface=eth0` を指定し、radio index 0/1/2/3の実験用名称を対応させる。ダミーinterface名を書いただけで実hostapd/Wi-Fiが起動するわけではない。Controller管理モード、Agent管理モード、同一Network上のwire trackingを上流設定に合わせて試験する。

## 実行例（隔離ホストのみ）

```sh
# upsteam / target deps のprivate stageを用意した環境でのみ
PRPLMESH_AMX_LAB_UBUS=1 \
  packaging/easymesh/build-prplmesh-nl80211.sh \
  <exact-6.0.1-source> <hostapd-2.12-layout> \
  <amx-target-prefix> <isolated-build-dir>

python3 packaging/easymesh/run-easymesh-two-node-lab.py \
  --controller-image <prebuilt-local-runner-image> \
  --agent-image <prebuilt-local-runner-image> \
  --install-tree <private-install-stage-prefix> \
  --install-target <compiled-cmake-prefix> \
  --controller-al <controller-AL-MAC> --agent-al <agent-AL-MAC> \
  --amx-ubus \
  --controller-platform-db <private-0600-controller-DB> \
  --agent-platform-db <private-0600-agent-DB> \
  --controller-db-command 'beerocks_cli -c bml_conn_map' \
  --output <new-private-output-directory> \
  --duration 60 --outage 60 --execute
```

このLab runnerはController+Agentコンテナ1つと別Agentコンテナ1つを実起動する。初回pcap、Agent停止中pcap、Agent再起動pcapを収集し、各種daemonの `/proc/PID/exe`、双方向Discovery、Topology Query/Response MID、DB初回登録/消失/復帰を分離して検証する。結果と生ログはprivate出力のままにし、GitHubへはMAC/秘密/生PCAPを含まない要約だけを転記する。

### 受入と残リスク

| Gate | 必要な観測 | 現在 |
|---|---|---|
| AMXRT backend | 実process内でbackendロードとbus接続、controller起動 | NOT_PROVEN |
| radio 2/3 | 実Agentでindex mappingが成功し、retryが解消 | NOT_PROVEN |
| 1905 transport | 独立netnsの実 `0x893a` が両端から送信 | NOT_PROVEN |
| discovery/topology | Controller/Agent別ALと Query/Response MID 一致 | NOT_PROVEN |
| Controller DB | Agentの登録、消失、再登録 | NOT_PROVEN |
| Agent recovery | 同一ALの再起動後、wire/topologyとDB復帰 | NOT_PROVEN |

**最初の失敗箇所を最優先で追跡**。 `No backends specified` が残れば、moduleのelf arch・依存ライブラリ・コンパイル済み `AMBIORIX_BACKEND_PATH`・ubusd socketを順に調べる。Agentがretryならprivate DBの `wireless_interface_0..3` とLinux netdev実在・control socketを照合する。1905が0なら `br-lan`/ `eth0` 実bridge membership、upstream設定のuntracked interface表示、送信側netns内のPCAPを検査し、**キャプチャ経路不一致と送信ゼロを区別**する。

C号機・A号機・raspi4、PR #13、mainへの書込み・mergeは禁止。今回のhost試験の合格はwire成功とは別。PR #13へは本Draft PR #17の差分・証拠だけを引き渡す。
