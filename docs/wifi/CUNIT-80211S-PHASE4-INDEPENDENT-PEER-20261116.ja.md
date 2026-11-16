# C号機 802.11s 第4段階: 独立peer実証・2.4GHz実機準備ランブック

更新: 2026-11-16。基準は[統合PR #13](https://github.com/Karin-Laboratory/Debian13-Terminal6/pull/13) HEAD `33102b1`。このブランチの試験対象は**隔離したLinux/hwsimのみ**。C号機/A号機/raspi4の状態には変更を加えない。

## 第4段階の実CI受入記録

**最終確認**: [Actions #43808587584](https://github.com/Karin-Laboratory/Debian13-Terminal6/actions/runs/43808587584) は全3ジョブSUCCESS（2-node、3-node独立VM×2）。監視器付き復旧は5.094 / 5.111秒、両VMで`HWSIM_PCAP_AUDIT=PASS`、`HWSIM_AMPE_FRAME_PROTECTION=ONWIRE_MIC_FORMAT_PASS_CRYPTO_MIC_UNVERIFIED`。これは独立AES-SIV MIC検証ではなく保護形式のフレーム観測である。A/C実機でのRF通信は未実施。



- [Actions #43808405316](https://github.com/Karin-Laboratory/Debian13-Terminal6/actions/runs/43808405316) **全3ジョブSUCCESS**。2-node smokeはSAE-configured peering、双方向IPがPASS。独立2VMの3-nodeではwmediumdでA-C遮断、HWMP A↔C next hop B、双方向ping、B停止時の断、復旧後のpeer/IP/HWMPをすべて確認。
- `mesh_peer_autorejoin.py`の監視器がBのDOWN→UPを検知し、`mesh_group_remove/add`を**無人実行**。SUPERVISED_AUTO復旧2/2 PASS、B UP後 5.114 / 5.095 秒、復旧後20/20 ping・0% loss、RTT平均 2.511 / 2.047ms。**native自動復旧をPASSとはしない**（監視器ありの試験なので今回はNOT TESTED、PR #11ではnative FAIL）。
- `hwsim0`で取得した一時PCAPを公開せず、別処理でSAE auth algorithm 3、Self-protected Mesh Peering Open/Confirmの**MIC IE ID 140、16バイト**、Protected-bit付きDataを2送信元で確認。`HWSIM_PCAP_AUDIT=PASS` 2/2。**AES-SIVのMICを独立復号・暗号学的検証したものではない**。
- 初期のcapture失敗とAMPE MIC判定FAILは、hwsim monitorのUP設定不足と検査器のEID `76`誤記が原因だった。Linux `WLAN_EID_MIC=140`へ修正し、CIの反復で確認。失敗したrunは成功へ読み替えない。
- A/C実機、raspi管理系、6GHz RF、slot/P25/eMMC、MLO、EasyMeshへの操作は一切行っていない。**C号機との実RF peeringはNOT TESTED**、対応USBアダプターの現物検証・調達も未達。

## 最新の実機事実と既存成功を再利用

- C号機は署名済みP25で起動済み。`CONFIG_MAC80211_MESH=y`、`iw phy`の`mesh point`能力と、一時interfaceの生成・削除は実機PASS。これは**SAE/AMPE、mesh peer、RF、IP、HWMPの成功証拠ではない**。
- C号機の管理LAN/SSH/UART、eMMC 100MHz/no-CQE、slot B復旧経路を守る。`wlp1s0` DOWN、実peerは未準備。6GHz全チャネルの送信許可はなく、320MHzも使用しない。
- [PR #11 の独立3VM結果](CUNIT-80211S-PHASE3-EVIDENCE-20261116.ja.md)ではA-B-C HWMPと**明示的**`mesh_group_remove/add`復旧3/3 PASS、無操作のnative recovery FAIL、AMPE保護の独立確認不足。
- 最新のC号機事実は[統合実測記録](../integration/CUNIT-WIFI-INTEGRATION-20261116.ja.md)の末尾節を優先し、古い「mesh kernel未反映」の記録を現行と取り違えない。

## オフライン実通信ゲート

| 判定対象 | 合格証拠 | 注意 |
|---|---|---|
| 2-node SAE/IP | 別network namespaceの2 PHYで両側peer CONNECTED、両方向ping | `key_mgmt=SAE`文字列だけは不可 |
| 3-node HWMP | `wmediumd`でA-Cリンク100%遮断、A↔C双方向IPとnext hop=Bを両方向検証 | 単純な同一SSID接続では不可 |
| AMPE on-wire | hwsim0 PCAPに2送信元のSAE auth、mesh peering Open/ConfirmのMIC IE(140/16byte)と保護Data | MIC存在はAES-SIVの独立復号/真正性証明そのものではない |
| native automatic recovery | 監視器・明示API呼出し無し、DOWN/UPのみでpeer/IP/HWMP復旧 | 第3段階では3/3 FAIL |
| supervised automatic recovery | 起動済み監視器がBのDOWN→UPに反応し、上流mesh group再参加を自動実行→peer/IP/HWMP復旧 | **nativeとは別ラベル**。監視器が動いたことをreceiptで証明 |
| assisted recovery | 人間/試験スクリプトが明示的にmesh group再参加→peer/IP/HWMP復旧 | 第3段階でPASS済み |

新たな802.11s/MAC/HWMP/SAE実装を作らない。[既存3ノード試験](../../scripts/run_80211s_hwsim_3node.sh)を再利用し、[監視器](../../scripts/mesh_peer_autorejoin.py)と[PCAP検査器](../../scripts/mesh_peer_capture_audit.py)のみ局所追加。[第4段階Actions](../../.github/workflows/cunit-80211s-phase4-independent-peer.yml)は2ノード、3ノード反復、AMPE-on-wire、復旧分類を独立チェックする。生PCAP/秘密PSK/MACログはアップロードせず、サマリーのみ残す。

実行例（**物理PHYが存在しない独立VMのみ**、既存`hwsim0`・実無線PHYがあるVMではスクリプトが拒否する）:

```bash
sudo apt-get install iw iproute2 iputils-ping kmod wpasupplicant openssl tcpdump
# wmediumdは既存ActionsでPINした上流commitを別途ビルド
sudo env CUNIT_MESH_SUPERVISOR=1 CUNIT_MESH_CAPTURE_AUDIT=1 \
  timeout --signal=TERM --kill-after=5s 420 bash scripts/run_80211s_hwsim_3node.sh
```

本ブランチの`mesh_peer_autorejoin.py`は`cmesh-*`namespaceの`meshB`以外を拒否する**ホスト試験専用品**で、C号機で無断起動・常駐させるものではない。

## 実機peer候補・必要機材

**推奨の最小構成**: C号機とは別のLinux小型機またはVMにUSB Wi-Fi passthrough付きの独立Linuxマシン1台、**mac80211 802.11s mesh point対応2.4GHz無線アダプター1本**、アンテナ・対応firmware・有線管理経路。候補はAtheros AR9271 USB / Linux `ath9k_htc`、firmware `htc_9271.fw`。Linux Wireless公式[ath9k_htc説明](https://wireless.docs.kernel.org/en/latest/en/users/drivers/ath9k_htc.html)はMesh Modeを記載。ただし**現物のVID:PID/改版、`iw phy`、SAE/AMPE、実RF peeringは購入・接続後に確認が必要**で、商品名だけではPASSにしない。

- 既存raspi4はC号機の管理LAN/復旧経路なので、管理中のWi-Fiや有線NICをメッシュ用に転用しない。余剰raspi等があれば**独立USB無線IFだけ**を専用peerへ割り当てる。
- Raspberry Pi内蔵`brcmfmac`はmesh point能力が期待できないため、`iw phy`で確認できるまでは対向peerに数えない。AR9271系は2.4GHz用途で、5GHz/6GHzに対応するとは扱わない。
- C号機を加えたA-B-C実無線マルチホップには、少なくとも**C号機 + 独立したmesh point 2台（計3ノード）**が必要。A-C間の直接RF遮断を実測で立証できる配置・遮蔽・減衰手段と、各ノードの**有線**管理/復旧経路も別途必要。
- A号機の純正MediaTek `mt_wifi`/EasyMesh/APの観測に`mesh point`、SAE/AMPE、HWMP peeringがない。**A号機は現時点で802.11s対向機として未認定**。純正EasyMeshを802.11sとみなさず、A号機は読み取り専用。

独立Linux peerに接続した**後**、無線送信なしで候補PHYを監査する（`phyN`は当該USBアダプターと読み取り照合して置換）。

```bash
iw dev
iw phy phyN info
iw reg get
bash scripts/mesh_peer_readonly_preflight.sh phyN
command -v wpa_supplicant
```

最低限`mesh point`、2.4GHz対象チャネルの許可条件、channel flags（`disabled`/`no IR`を含む）、PHYの同時interface制約、firmwareロード、wpa_supplicantのmesh/SAEサポートを確認。送信前にC号機・対向機それぞれの技適/使用条件を確認し、ドライバ能力だけを法的な送信許可と扱わない。

## 2.4GHz実通信に移る場合の設定ひな形（**今回未実行**）

mesh IDとPSKはC号機・独立peerで一致させる。`mode=5`は802.11s、`key_mgmt=SAE`はSAE、`mesh_fwding=1`は中継許可。`2437`MHzは例示の2.4GHz ch6で、実際には両機のregulatory/ch flagsと周囲の電波状況に応じて選ぶ。C号機へ新たにパッケージを入れたり、既存STAをdownしたりしない。変更が必要な時点で別作業・個別承認とする。

```ini
# peer側 /run/cunit-mesh-peer.conf、所有者root、mode 0600
ctrl_interface=/run/cunit-mesh-ctrl
network={
    ssid="cunit-80211s-lab"
    mode=5
    frequency=2437
    key_mgmt=SAE
    psk="REPLACE_WITH_PRIVATE_RANDOM_PASSPHRASE_ON_BOTH_PEERS"
    mesh_fwding=1
}
```

送信条件の承認・機材準備が済んだ**別作業**では、まず独立Linux peerのみで`iw phy phyN interface add mesh-peer type mp`、有線管理維持を確認して`wpa_supplicant -Dnl80211 -i mesh-peer -c /run/cunit-mesh-peer.conf`の実行と、peerの状態・保護フレーム・双方向IPを記録する。秘密値はroot-onlyの揮発領域で生成・保管し、公開CIやPRに貼らない。C号機側のjoinは別の実機許可を待つ。C用IP例`10.253.44.1/30`、peer用`10.253.44.2/30`（別の既存routeと衝突しないことを確認）。

**セキュリティゲート**: 2026-07-29公表の[hostap AMPE処理の長さ検証不備](https://w1.fi/security/2026-4/)を修正したwpa_supplicant（v2.12以降またはバックポートパッチ適用確認）が、RFへ参加する全peerに必要。Ubuntu runnerでの隔離hwsim評価を、そのまま未修正の実RFサービスへ移してはいけない。

## 統合条件と境界

- 今回の範囲はhost-only仮想実通信とpeer設定/機材確定まで。C号機のRF、slot、P25、P26、P44、regdb、EEPROM、管理経路は変更しない。
- 各結果は`PASS / FAIL / BLOCKED / NOT_TESTED`で記録し、監視器による自動復旧を『wpa_supplicant native automatic recovery』と表示しない。PCAP上のMIC確認と独立AES-SIV暗号学的検証も区別する。
- PR #13へはレビュー・統合可能な別Draft PRで提出し、主担当の明示的な引継ぎがあるまでマージしない。mainへ直接マージしない。
