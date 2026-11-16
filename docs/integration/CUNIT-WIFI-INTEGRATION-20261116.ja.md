# C号機 Wi-Fi統合Draft: マージ状況と実機受入 (2026-11-16)

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

実機書込み前の残ゲート:

1. 更新した`replay_80211s_kernel_source.py`と再構成ツールを含む統合ブランチCIをPASSさせる。
2. ビルドImage・modules、100MHz/no-CQE DT、既存initramfsと署名済みregdbの組合せを検証し、正確なunsigned P25を製造する。
3. そのP25の正確なSHAに対応する保護署名と独立receiptを確認し、slot B起動・電源サイクル復旧条件が引き続き使えることを照合する。boot_a以外、boot_b、校正/OEM領域は書かない。
4. 実機へ接続できる管理経路から適用後、reboot後のMESH_POINT、160MHz/no-320、regdb、eMMC、SSHをread-onlyで確認する。
5. 独立802.11s peerまたはMLO端末を用いた実通信を行う。EasyMeshは実control socketと2ノードpeerが揃うまでhost成果と分ける。

この時点では全PRのコードと検査を統合ブランチへ入れ、host上で再現可能なkernel buildまで確認したが、**統合実機機能をmainへ取り込む準備は未完了**。各個別PRと統合PRはDraftのまま保持し、機能PASSを確認できた範囲だけ後続コミットで更新する。
