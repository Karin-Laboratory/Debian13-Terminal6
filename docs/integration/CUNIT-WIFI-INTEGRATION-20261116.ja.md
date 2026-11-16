# C号機 Wi-Fi統合Draft: マージ状況と実機受入 (2026-11-16)

> **Codex再開手順:** [C号機Wi-Fi統合ランブック](CUNIT-CODEX-RUNBOOK.ja.md) に沿って、前回との差分だけを確認し、最初の未達ゲートから再開する。過去の成功工程・失敗解析を無条件で繰り返さない。

## 対象とブランチ

統合ブランチ `integration/cunit-wifi-mesh-mlo-20261116` は `main` の `e72894806933485a4b212f5d78f958fb1d27292e` から作成した。PRごとの現在のHEADを次の順で取り込んだ。PR #10 はPR #6を、PR #11 はPR #9を親履歴として含む。Gitの祖先関係を保持してマージし、ファイル差分を二重適用していない。独立しているPR #12は最後に統合した。

| PR | 開始時のHEAD | 内容 | 統合方法 |
|---|---|---|---|
| #6 | `f0d561770db59eeaf6ccf4d4a8345961e6ee0508` | 6GHz/regdb、160MHz・no-320、Wi-Fi監査 | mainへmerge |
| #9 | `a1f0c88bad662a37bd9aaeeb6ffcee9796ca88c5` | EEPROM/OTP初期化、校正timeout、link checker | PR #6の後へmerge |
| #10 | `a3789dff9c24523e11a61a694023978298a0ca69` | MLO topology、受入判定、hwsim | 先行するPR #6/#9の祖先を利用してmerge |
| #11 | `5ac8837276835e59f7a825dad973024da9cf773b` | 802.11s、HWMP、hwsim/再現性検査、追試記録 | PR #9の祖先を利用してmerge後、最新追記もmerge |
| #12 | `852e4446a541f0fe4a260c71a97be978d87666e3` | prplMesh EasyMesh、ARM64 packaging/preflight | mainからの独立変更を最後にmerge |

競合は`.gitignore`と`CHANGELOG.md`のみ。除外規則は統合し、履歴説明は各PRの内容を残して解決した。既存PRは閉じず、mainへはマージしていない。

統合PR作成後にPR #11へ追加された上記HEADも統合ブランチへ取り込んだ。PR #13の初回`host-tests`はrun `43789317941`でPASS。後続コミットを含む統合branchのrun `43794474355`もPASS。

## 現在のC号機ベースライン

- Debian 13、Linux `6.18.63-debian-t6-proto2 #4`、起動slot A。`boot_a`は署名済みP25 SHA256 `8457ae5b31d38a754442ed0826544e19cf262059d8578b1eb0218d1cc3f2beb8`と一致。
- C側管理Ethernetは`lan2` / `192.168.3.1/24`、default routeは`192.168.3.71`経由。別bridgeはなく、既存のraspi4直結経路を維持。Wi-Fiは`wlp1s0` DOWN。
- eMMCはHS400、8-bit、1.8V、requested 100MHz / actual `94,999,965 Hz`、`cmdq_en=0`。P44はRWで1.7GB空き。再起動後の新規MMC/CQE/ext4 I/O errorなし。
- PHYは`phy0` 1つ。Band 1=2.4GHz、Band 2=5GHz、Band 4=6GHz。PCI function 7990/7991の存在から、独立した2つの無線PHYとは推定しない。interface combinationは`#channels <= 1`。
- Wi-Fi driverは`512937107627c2fcd075d8a36cf2573d024f3e3d9da94a741650071f04527990`のno-320 host buildに差し替え済み。`terminal6-wifi-phy.service`用SHA一覧を更新し、通常再起動後もロード、160MHz能力を保持、320MHz EHT能力を非広告と確認。
- regulatoryはglobal `00`。2.4GHz ch1–11はIR可、12/13はno-IR。5GHzは確認範囲でno-IR、6GHzは全チャネルdisabled。cfg80211は起動時にregdb署名不正を記録。6GHz RF送信なし。
- `hostapd`, `wpa_supplicant`, prplMesh daemonsおよびそれらのcontrol sockets/servicesはC号機に見つからなかった。今回新たに無線サービスを導入・起動していない。
- UART経路は既知のraspi4復旧経路として保持。今回の受入サイクルではUART出力採取を実施していない。A号機は読み取り専用条件を維持し、今回新しい操作・比較採取を行っていない。

## 機能別受入結果

| 機能 | 状態 | 証拠・未達 |
|---|---|---|
| 2.4/5GHz STA/AP | BLOCKED | 実機にhostapd/wpa_supplicantとpeerがない。今回association/IP通信をしていない。管理経路は有線維持。 |
| 6GHz 160MHz | PARTIAL | capability 160MHz、no-320、再起動復帰は実機PASS。regdbはuntrusted signerで失敗し、6GHz全チャネルdisabled。AP/STA、association、IP通信、実リンク幅は未実施。 |
| MT7990 EEPROM/OTP初期化 | PARTIAL | reboot logでEEPROM 8ページupload、46 OTP calibration-free bytes mergeを確認。ただし同時にEEPROM default-bin fallback logあり。個体校正全体の適用成功とはしない。 |
| IEEE 802.11s / HWMP | BLOCKED | 稼働kernelは`CONFIG_MAC80211_MESH`なし。実`iw phy`のinterface modesにMESH_POINTなし。PR #11 config fragmentを有効化するにはkernel/P25変更が必要。独立peerがないため実機通信なし。 |
| MLO | BLOCKED | driver sourceには`WIPHY_FLAG_SUPPORTS_MLO`があるが、C号機の同一MLD/link ID、2 active link、link別counter、データ通信を示す実測なし。hwsim Actionも失敗・cancelled。1 PHY / `#channels<=1`だけから複数独立linkを推定しない。 |
| EasyMesh / IEEE 1905 | BLOCKED | prplMesh 6.0.1のAArch64 build/ELF監査とhost testsは成功。C号機のbinary/process/control socketなし。有線Discovery/Topology、Controller DB、Agent再接続、無線backhaulは未実施。 |
| eMMC・有線管理 | PASS (baseline) | 100MHz制限/CQE無効、P44正常、管理Ethernet/SSHは再起動後復帰。UART出力は未採取。 |

## CIとhost検証

- 統合後のunittestは138件PASS。`compileall`、mesh/EasyMesh shell syntaxもPASS。最初の実行は環境の`/tmp/.git`をテストが実checkoutと誤認したため、`TMPDIR=/var/tmp`で再実行してPASS。
- 802.11s: run [43787300664](https://github.com/Karin-Laboratory/Debian13-Terminal6/actions/runs/43787300664) の3独立VM trialは全てPASS。これはhwsimでの**assisted** mesh rejoinとA↔C IPのみ。automatic recoveryは同試験記録でFAIL、AMPE frame protectionとC号機RFは未検証。PR #11 host checks [43787667492](https://github.com/Karin-Laboratory/Debian13-Terminal6/actions/runs/43787667492) PASS。
- EasyMesh: PR #12 host checks [43787213765](https://github.com/Karin-Laboratory/Debian13-Terminal6/actions/runs/43787213765) PASS (24 testsを記録)。ARM64 build/ELF loader auditはhost成果で、C号機process起動や1905 packetの実測ではない。
- MLO: run [43785577376](https://github.com/Karin-Laboratory/Debian13-Terminal6/actions/runs/43785577376) はhwsim実行段階でcancelled。直前の完了run [43786976450](https://github.com/Karin-Laboratory/Debian13-Terminal6/actions/runs/43786976450) は`eht_mld_owe_two_links`でFAILし、5/6GHz 160MHz fixtureは実行されなかった。現在のPR #10 HEAD `a3789dff…`に対するActions runは見つからず、受入PASSとはしない。

## Kernel source / 次の実装ゲート

正規Linux 6.18.63 tarball SHAは`81764a545072d160748beff4d9de2e7d95aa9f16e8261110288f067a2cc61d71`。従来の逆適用方式はPR #9 patchと所有者スナップショットの文脈が異なり失敗したため、private-only完全スナップショット差分の経路を追加した。`.gitignore`対象のソースも漏れなく扱うよう修正し、合成テストで確認した。privateソースの内容・差分はGitHubへ置かない。

次にPR #6 no-320変更をスナップショットへ意味的に適用した後、正規tarから更新済みソース全体を再生し、全ファイルインベントリが一致した。PR #9とvendor差分の独立来歴は分離できていないため、再現成功は「正規tarからprivate snapshotまでの一致」に限定する。

独立ARM64ビルドは`CONFIG_MAC80211_MESH=y`、`CONFIG_MT7996E=m`、`CONFIG_CFG80211_REQUIRE_SIGNED_REGDB=y`を含む設定で`olddefconfig`変更なし、`Image`と必要なmt76 modulesのビルドがPASS。正確なartifact SHAとsource replay receiptはprivate領域に保管する。これはホストビルド成果で、P25署名、実機起動、MESH_POINT登録、RF通信を証明しない。

### 2026-11-16 実機再確認と候補イメージ

- raspi4経由SSHでC号機を読み取り確認。slot A、kernel `6.18.63-debian-t6-proto2 #4`、有線`192.168.3.1/24`、default route `192.168.3.71`、P44 ext4 RW、1.7GB空き。`boot_a`の実測SHA256は`8457ae5b31d38a754442ed0826544e19cf262059d8578b1eb0218d1cc3f2beb8`。eMMC actual clock `94,999,965 Hz`、HS400/8-bit/1.8V、`cmdq_en=0`相当の既存no-CQE状態。採取時のkernel logでDATA TIMEOUT/CQE recovery/I/O error/ext4 errorは0件。
- 期待と異なり、稼働中`/proc/config.gz`には`# CONFIG_MAC80211_MESH is not set`。`iw phy phy0 info`のsupported modesに`mesh point`はなく、無送信の`iw dev wlp1s0 interface add mesh-probe type mp`は`Operation not supported (-95)`で失敗した。試験interfaceは生成されず、既存`wlp1s0`と管理経路への変更なし。これはhost buildの`CONFIG_MAC80211_MESH=y`が実機に未適用であることを示す。
- C号機に`hostapd`、`wpa_supplicant`、`prplmesh`、`ieee1905d`実行ファイルは見つからず、起動中のWi-Fi/EasyMesh関連serviceもなし。IEEE 1905や無線実通信は未実施。
- 現行global regdomainは`00`、起動ログは`regulatory.db is malformed or signature is missing/invalid`、6GHz全チャネルdisabled。6GHz送信なし。
- regdb署名とmeshを含むunsigned P25候補は生成・構造検証済み。サイズ32MiB、SHA256 `83478d8804172777c9dc69fd35a1e3931257a130a5c803e588b6e286c390cd2e`。この候補には正確なSHA向け署名がまだなく、未署名・未適用・未起動である。署名済み旧候補の署名を流用しない。
- 現在のprotected signing workflowは過去の別SHA/DTB/一回限りmarkerへ固定されているため、この新候補を署名できない。新候補を正確なdigest・DTB・initramfs・専用one-shot markerに固定した同等以上の保護workflowを用意し、既存署名系のsource pins、shared lock、独立RSA-PSS検証を維持する必要がある。新候補の署名とboot_a書込みはまだ行っていない。

実機書込み前の残ゲート:

1. 更新した`replay_80211s_kernel_source.py`と再構成ツールを含む統合ブランチCIをPASSさせる。
2. ビルドImage・modules、100MHz/no-CQE DT、署名済みregdbの組合せを検証し、正確なunsigned P25を製造する。現在の候補は構造検証済み。
3. 新候補SHAに固定した保護署名workflowと独立receiptを確立する。現在の旧workflowは異なるdigest/DTBに固定され、新候補には使えない。署名後、slot B起動・電源サイクル復旧条件が引き続き使えることを照合する。boot_a以外、boot_b、校正/OEM領域は書かない。
4. 実機へ接続できる管理経路から適用後、reboot後のMESH_POINT、160MHz/no-320、regdb、eMMC、SSHをread-onlyで確認する。
5. 独立802.11s peerまたはMLO端末を用いた実通信を行う。EasyMeshは実control socketと2ノードpeerが揃うまでhost成果と分ける。

この時点では全PRのコードと検査を統合ブランチへ入れ、host上で再現可能なkernel buildまで確認したが、**統合実機機能をmainへ取り込む準備は未完了**。各個別PRと統合PRはDraftのまま保持し、機能PASSを確認できた範囲だけ後続コミットで更新する。

## 2026-11-16 追加実機適用・再確認 (後続結果が上記の古い状態を更新)

### P25・slot・復旧

- 正確なSHA `83478d8804172777c9dc69fd35a1e3931257a130a5c803e588b6e286c390cd2e` の32MiB候補を、保護された署名workflowで署名し、独立RSA-PSS検証をPASSした。署名済みP25のSHA256は `ae65d0c28c5d3c6a0189193c70f3783c142da3c97553bb8fe80059569046dea0`。署名レシートとバイナリはprivate Draft PR #159/releaseに保持。
- 純正slot B起動後、PARTNAMEで特定した`boot_a`だけを更新し、全32MiBのreadback SHA256一致を確認。`boot_b`とP26/P44/OEM/GPTは変更なし。純正`quec_bootctrl`でslot Aを選択し、Debianへ復帰した。slot Bの既知ED25519ホスト鍵を既存known_hostsと照合して検証した。
- 起動後はDebian 13、kernel `6.18.63-debian-t6-proto2 #2`、SSH/管理Ethernetが復帰。P44はext4 RW。eMMCはHS400/8-bit/1.8V、実測 `94,999,965 Hz`、CQE無効。候補DTの100MHz上限が反映されている。稼働中kernel configは`CONFIG_MAC80211_MESH=y`、`CONFIG_CFG80211_REQUIRE_SIGNED_REGDB=y`。
- P25の署名・readback・A/B起動確認はPASS。今回この作業単位ではUARTのシリアル出力を再採取していない。

### 修正済みmt76モジュールと802.11sの実機確認

最初のprivate kernel-source replayにはPR #9のOTP校正パッチが含まれていないことを実機ログから発見した。その試行のモジュールを退避し、公開統合ブランチの`patches/0001-mt7996-eeprom-calfree-timeout.patch`をprivate sourceへ適用、mt76外部モジュールを再ビルドした。以後の実機結果はこの修正版を対象にする。モジュールSHAはP44上の`MODULE-SHA256SUMS`と照合し全件PASS。

| モジュール | SHA256 |
|---|---|
| `mt76.ko` | `820d09afadd41dbd47427b479c2eaba0b1ee1fab88dd8c3a1a530db80e2a86f2` |
| `mt76-connac-lib.ko` | `e8e0a5c7b0dd09b977e5454819e9f7aa5cb896bab58872df8a17bcb73369a64c` |
| `mt7996e.ko` | `42411e3a9941f36d6997bd78828c44165d2a55abdbbd0353c39e2427edc88cc9` |

修正モジュールは再起動後に`terminal6-wifi-phy.service`から正常ロードされ、firmware/EEPROM初期化ログでは46 OTP由来校正byteの統合とEEPROM 8/8ページのuploadを確認した。`iw phy phy0 info`は`mesh point`を広告し、`iw dev wlp1s0 interface add mesh-probe type mp`、interface情報の取得、削除が成功した。元の`wlp1s0`はDOWNのまま、mesh試験interfaceもDOWNで削除済み。これは802.11s interface capability/生成のPASSであり、peer発見、SAE/AMPE、ESTAB、HWMP、IPデータ通信、再接続の実通信を意味しない。

### 最新の無線・regdbゲート

- 起動ログにcfg80211がcompiled-in X.509証明書を読み込む記録があり、今回の起動ログでは以前の`regulatory.db is malformed or signature is missing/invalid`は見つからなかった。これは起動時の署名鍵読み込みの観測である。
- `iw reg get`は依然global `00`。6GHzチャネルは規制状態で利用不可。今回の確認だけでは署名済みregulatory.db適用と国内の認可ドメイン確立をPASSにしない。6GHz送信は行っていない。
- 現在のdmesgで`DATA TIMEOUT`、`CQE recovery`、MMC/ext4 I/O error、regdb malformedの新規一致は0件。Wi-Fi PHYは`phy0`、interface `wlp1s0` DOWN。RF送信なし。
- 2.4/5GHz STA/AP、mesh peer間通信、EasyMesh/IEEE 1905、MLOのMLDリンク通信は未達。利用可能な独立peer/control endpointがないため、能力表示やhost CIを実機通信PASSに読み替えない。

### 受入状態の更新と復旧

| 機能 | 最新状態 |
|---|---|
| 署名済みP25適用・slot A復帰 | PASS (boot_a全量readback一致、slot B保持) |
| 管理Ethernet/SSH・P44・eMMC制限 | PASS (上記採取時点。UARTは今回再採取なし) |
| MT7990初期化・EEPROM upload | PARTIAL (46 OTP byte統合、8/8 page upload。default-bin fallback等の全校正評価は未完了) |
| 802.11s mode/interface作成 | PASS (interface DOWNで生成・削除、無送信) |
| 802.11s peer/SAE/AMPE/HWMP/IP/recovery | BLOCKED (独立mesh peerなし、次は適法な2.4/5GHz peerで段階試験) |
| 6GHz 160MHzの実通信 | BLOCKED (global 00、チャネル利用不可、送信禁止ゲート維持) |
| EasyMesh / MLO実機通信 | BLOCKED (独立対向機と実control/data試験なし) |

module rollback copyとP44のチェックサム一覧、およびslot/P25 backupはraspi4のprivate directoryに保管。module差替え時に生成した`modules.*` indexはPCI modaliasによる早期自動ロードを避けるため削除した状態を維持する。`depmod`を実行せず、現行`terminal6-wifi-phy.service`がP26からfirmwareを`/run`へstageしてから手動`insmod`する順序を保つ。失敗時は保存済み旧module一式・旧checksumへ戻して再起動する。P25復旧は検証済みslot Bと純正`quec_bootctrl`を使う。

したがってPR #13は引き続きDraftであり、mainへ統合できる実機受入完了状態ではない。今回完了したのは署名済みP25の実機起動と、mesh capability/interfaceの無送信試験まで。次の具体的な工程は、独立した802.11s peerを用いる2.4GHzまたは許可された5GHzでのpeer形成・保護・双方向通信、続いてEasyMeshの有線1905 discoveryとMLO対向機試験である。

## 2026-11-16 午後: hwsim MLO再現とEasyMesh runtime試行

### 現状・CI

- この記録更新時、C号機をraspi4経由read-onlyで確認: slot A、kernel `6.18.63-debian-t6-proto2 #2`、`boot_a` SHA `ae65d0c28c5d3c6a0189193c70f3783c142da3c97553bb8fe80059569046dea0`。SSH/有線route維持、`wlp1s0` DOWN、eMMC HS400/8-bit/1.8V、clock `94,999,965 Hz`、100MHz制限、CQE無効。DATA TIMEOUT/CQE recovery/MMC/ext4 error grepは0件。RF送信なし。
- PR #13 head `643033d9dae1020acdaf606b6587e5c1831e3428` のhost checks run `43802059437` PASS。main未マージ、Draft継続。

### MLO hwsim失敗の原因と修正

- 以前のMLO Actions run `43786976450`は`eht_mld_owe_two_links`で失敗し、後続試験を止めていた。pinned hostap commit `f1e9b5086718ad567dc40e3d5a1456534d51749f`をagent-101-vm kernel `6.12.101+deb13-amd64` (MLO対応`mac80211_hwsim`、`mlo`/`multi_radio`/`channels`)で再現した。
- 最初の停止原因はworkflowのPython依存不足で、hostap test discoveryがPyCryptodome importに失敗していた。workflowへ`python3-pycryptodome`を追加し、`vm_probe`が依存不在を試験前に報告するよう修正した。
- 依存追加後にMLD associationは成功した。次の失敗は、upstream `test_eht.py`が`CONFIG_MAC80211_DEBUGFS`なしの際、未定義`logger_info`を呼ぶことだった。さらにdebugfsの`valid_links` fileがないと、リンク状態のfallbackもなかった。`patches/hostap/0001-hwsim-use-MLO-STATUS-without-mac80211-debugfs.patch`でtypoを直し、wpa_supplicant `MLO_STATUS`からlink ID bitmapを読む局所fallbackを追加。workflowはpinned sourceへこのpatchを適用する。
- 修正後の実hwsim smoke runで`eht_mld_owe_two_links`, `eht_mld_link_removal`, `eht_mld_disassociate`が3/3 `SMOKE_PASS`。`cunit_mlo_5g160_6g160`は隔離hwsim VMのみでsynthetic `CA` regdomainを使い、`WIDE_MLD_IP_PASS`、STA→AP 6/6、AP→STA 6/6。これはシミュレートradioでのhost/hwsim結果であり、C号機の実RF、国内認可、MLO acceptance v2を証明しない (`acceptance_v2=NOT_PROVEN`)。

### EasyMesh有線1905 runtime試行

- private prplMesh 6.0.1 ARM64 install tree、既存Debian arm64 sysrootとprivate target librariesを隔離stageにまとめ、`ieee1905_transport`, `beerocks_controller`, `beerocks_agent`, `beerocks_vendor_message`のtarget loader resolutionが4/4 PASS。QEMU-userではtransport process単体の起動・SIGTERM終了も確認した。
- 続いてagent-101-vm内の一時network namespaces、veth、bridgeだけでController/Agentを分離し、C号機・raspi4・管理LANへ接続せず、EtherType 0x893a captureを試行した。ControllerはAMXRTの`No backends specified`で初期化失敗。Agentは設定されたradio index 2/3のinterface mappingがなくretryを続け、transportは`eth1`/`br-lan`をuntrackedとして無視した。PCAPは24-byte global headerのみで、IEEE1905 Discovery/Topology packetなし。**EasyMesh wire testはFAIL/未成立**。名前空間、process、captureは停止・削除済み。
- 次の実装条件は、AMXRT backend/pluginとcontroller/agent runtime configをstageに含めること、private platform DBでradio index→test interface mappingを与えること。これらを揃えて再度2-node wire captureとController DBを観測する。wireは成立しても無線backhaul/fronthaul実通信とは区別する。

### 802.11s peerと現在の次ゲート

- C号機の実radioは引き続きDOWNで、独立mesh peerはこの実行環境から用意できていない。802.11s capability/interface PASSは維持するが、peer discovery、SAE/AMPE、HWMP、双方向IP、再接続はNOT TESTED。
- 6GHz送信なし。C号機SSH/有線route/eMMC状態はread-only再確認で維持。UARTシリアル出力はこの更新では未採取。
- host unit suiteは`TMPDIR=/var/tmp python3 -m unittest discover -s tests -p 'test_*.py' -v`: 139 tests PASS。デフォルト`/tmp`は環境内`.git`配置のため2 private-source testsが誤ってcheckout内扱いとなる既知のローカル一時ディレクトリ問題。
