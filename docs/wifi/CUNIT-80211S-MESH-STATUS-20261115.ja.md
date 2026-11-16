# C号機 IEEE 802.11s mesh 状況 (2026-11-15)

## 現時点の判定

| 段階 | 状態 | 根拠 |
|---|---|---|
| 802.11s実装の有無 | kernel/driver sourceには実装あり | Linux 6.18.63 mac80211 mesh core、HWMP、peer-link state machine、およびmt7996 mesh関連コードを確認。 |
| 保存済みDebian kernel config | **BLOCKED: `CONFIG_MAC80211_MESH`未設定** | PR #9用の6.18.63 build inputで`CFG80211=y`, `MAC80211=y`, `MT7996E=m`だが`MAC80211_MESH`はunset。mt7996のmesh interface advertisementとmesh-specific処理は`#ifdef CONFIG_MAC80211_MESH`でガードされる。 |
| 修正config候補 | host config resolution PASS | このブランチの最小fragmentは`CONFIG_MAC80211_MESH=y`のみ。隔離したKbuild source copyで`olddefconfig`後も有効で、source guardがPASS。 |
| ARM64 kernel/module build | **PASS (既存host artifact; source provenance incomplete)** | 保存済みreceiptと実物のImage/module SHAは一致し、ARM64成果物の存在は確認済み。ただし元のgitlessソースsnapshotを既知の配布tarから再現できないため、PR #9基準の再現可能ビルドとは認定しない。未署名・未パッケージ・未起動。 |
| hwsim 2-node mesh | **PASS (host synthetic)** | 2437MHz、wpa_supplicant SAE mesh設定、peer成立および双方向IP pingを実行。物理MT7990動作の証拠ではない。 |
| A号機 802.11s | UNKNOWN | 保存済み純正観測にはWi-Fi設定/PHY/APの情報はあるが、mesh point、peer、HWMP path、mesh dataの証拠がない。独自mesh/EasyMesh/WDS/802.11sのいずれかを推定しない。 |
| C号機 mesh peer / SAE / HWMP / IP | NOT TESTED | 実機操作を行っていない。 |
| 3-node multi-hop | **PARTIAL PASS (host only)** | 2026-11-16 hosted hwsim/wmediumd実行でA-B-C peering、A-Cの非直接通信とHWMP B経由、B down時の断を確認。B復旧はFAIL、AMPE独立検証・実機は未実施。 |

## A号機との比較

保存済みPR #6のread-only観測では、A号機はStock Linux 5.4.238のMediaTek proprietary `mt_wifi`/MT7990構成で、別PHYの2.4/5/6GHz表示とAP設定が記録されている。一方、IEEE 802.11s mesh-point interface、peer link state、HWMP route、4-address forwardingまたは暗号化mesh trafficは記録されていない。したがってA号機が802.11sを使用するとは言えない。純正のmesh marketing/mesh controller機能が観測されても、802.11s dataplaneと同一視しない。

## C号機 source audit

既存build receiptはLinux stable v6.18.63とPR #9のMT7996 EEPROM/OTP変更を含む入力snapshotと記録し、`1cdda838e8475edf89b73ff0cc952005dd0b1fa7`を既存receipt由来のbaseline SHAとして挙げている。ただしbuild用source copyにGit metadataがなく、このSHAと実際の全ソース内容の対応は独立確認されていない。2026-11-16の再監査で、保存済み標準Linux stable 6.18.63 tarはMT6990用vendor source/Kconfigを含まず、PR #9 patchだけを当ててもC号機向けkernel treeにはならないことを確認した。現在残るprivate build treeには`drivers/clk/mediatek/clk-mt6990.c`等のvendor sourceが存在し、`kernelrelease`は`6.18.63-debian-t6-proto2`だが、source commit/patch manifestは欠落している。したがって既存build artifactは実在するhost artifactとして扱い、正確なsource provenanceと再現性が回復するまでP25候補の製造・実機適用には使用しない。

- `net/mac80211/Kconfig`の`MAC80211_MESH`はboolで、802.11 mesh operationを有効にする。
- `net/mac80211/mesh.c`, `mesh_plink.c`, `mesh_hwmp.c`, `mesh_pathtbl.c`はmesh lifecycle、peering, HWMP, mesh path tableを実装する。
- `mt76/mt7996/init.c`は`CONFIG_MAC80211_MESH`条件でMESH_POINT interface type、mesh iftype HE/EHT capabilityを追加する。
- `mt76/mt7996/main.c`と`mcu.c`にはMESH_POINT interface/MCU経路があり、`mac.c`にはmesh + 4-address RX処理がある。
- このため最初の必要変更はkernel config fragmentであり、現段階ではdriver source patchは不要と判断する。configを有効にしたkernel/module buildと実機でのinterface creationを別々に確認する。
- Mesh SAEは`wpa_supplicant`のuserspace MPM / SAE / AMPE経路を使う候補。stock hostapd APではなくmesh用supplicant構成を用いる。暗号化を使う場合はSAE peer establishmentを直接確認する。

## 管理経路・周波数制約

最初の物理試験は、保存済みのC号機2.4/5GHz実通信実績を踏まえ、管理用Ethernetと干渉しない2.4GHzまたは許可条件確認済み5GHzの単一チャネルで行う。今のDebian環境では5GHz STA実通信が保存確認済みだが、チャネル availabilityはregulatory/NO_IR条件に依存する。6GHz送信は別途の個体認証・regdb gate完了前に行わない。

mesh interfaceを作っても、既存`wlp1s0`管理STAまたはAPを勝手にdown/replaceしない。実機の同時interface combinationと実利用可能PHY/radioをread-onlyで確認してから、独立管理経路の維持を条件に一時interfaceを追加する。eMMC/CQEに書込みエラーが続く間は、P44へのpackage installや永続化をしない。最初の試験はRAM/volatile stateに限定する。

## 成功判定

mesh support config、`iw phy` capabilityまたはmesh interface作成だけでは成功としない。以下を段階別に記録する。

1. mesh interface creation
2. peer state `ESTAB`
3. WPA3-SAE + AMPE secured peering
4. 2-node bidirectional IP traffic
5. HWMP path to a non-direct destination via next hop
6. 3-node multi-hop bidirectional forwarding
7. peer loss/recovery and route reconvergence
8. throughput/latency/loss and reboot persistence (別途安全条件を満たす場合)

## この作業での実機操作

この作業ではA/C unitの設定・無線送信・モジュール変更・再起動を行っていない。保存済みの過去結果を今回のlive testとして報告しない。許可されたraspi2経由でCの読み取り確認を試みたが、raspi2へのcodex接続後、Cの`root@192.168.3.1` SSH認証は`Permission denied (publickey)`となり、実機観測へ進めなかった。raspi4等の別経路は使用していない。今回のhost-only仮想試験は物理MT7990のdriver, firmware, board calibration, RF coexistenceを証明しない。

### Host synthetic test evidence

- `scripts/run_80211s_hwsim_smoke.sh`は隔離network namespace内の2台のmac80211_hwsim radioを使用。
- SAEで保護するmesh設定を適用し、両側peer接続イベントと双方向pingを確認。
- 結果：`HWSIM_80211S_SAE_CONFIGURED_PEERING=PASS`, `HWSIM_BIDIRECTIONAL_IP=PASS`, `HWSIM_FREQ_MHZ=2437`。
- cleanup後にhwsim module、network namespace、supplicant processが残らないことを確認。
- これは暗号化された物理MT7990メッシュ、HWMP複数ホップ、RF性能を検証しない。

### Isolated arm64 build evidence

- Source provenance: 保存済みLinux stable v6.18.63 tree (`1cdda838e8475edf89b73ff0cc952005dd0b1fa7`) とPR #9のmt7996 EEPROM/OTP修正を含む入力snapshot。build copyにはGit metadataがなかったため、基準SHAは既存保存記録から継承。
- Build input `.config` SHA-256: `1f70c927ea9ae20ec711506b6d63c9037d577c18b44c7e003ffe1a1cacd389b0` (`CONFIG_MAC80211_MESH=y`)。
- Baseline `.config` SHA-256: `b164811ae1a5246c694b641323f96e2e8f1842342529aea8e858dddb80f9887d`。
- Command: `make ARCH=arm64 CROSS_COMPILE=aarch64-linux-gnu- Image modules`, GCC 14.2.0; exit 0. Kbuild printed existing `MODULE_DESCRIPTION()` modpost warnings for unrelated configured modules; no build error.
- `arch/arm64/boot/Image`: 19,105,800 bytes; SHA-256 `904beb668b12bc508790555fe586da56179b440b60cc49900886493a1011aa81`.
- `mt76.ko`: 1,189,376 bytes; SHA-256 `ba53b88806e574d4eeab82d348b37cb81e04b85bf3fa309e6f7ecfd2f672031d`.
- `mt76-connac-lib.ko`: 625,040 bytes; SHA-256 `70d182716c6c77ca1bd1564a5971c4cde7eb12dc6bcd0f702e6566b9db5c75b4`.
- `mt7996e.ko`: 1,681,384 bytes; SHA-256 `d4431795a2395dfe1b2f28924eac6c3bf4ba053df9ab44b9a81d739133d9742b`; `readelf` identifies ELF64 little-endian AArch64 relocatable module. `vmlinux` contains mac80211 mesh path/HWMP symbols including `ieee80211s_init` and `mesh_path_start_discovery`.
- Build location: `/home/masataka/private/cunit-80211s-build-20261115/kernel-src`; binaries remain private and were not copied to the public GitHub repository or device.
- This is a host build only. No DTB pairing, initramfs, firmware bundle, signing, physical load, boot, or RF test was performed.

## 2026-11-16 source provenance re-audit

- 標準Linux stable 6.18.63 source archive: `/home/masataka/private/debian13-proto3-build-20261112/source/linux-6.18.63.tar.xz`, SHA-256 `81764a545072d160748beff4d9de2e7d95aa9f16e8261110288f067a2cc61d71`。このarchiveには`drivers/clk/mediatek/clk-mt6990.c`がなく、MT6990 vendor Kconfig/sourceも不足する。
- PR #9 headは`a1f0c88bad662a37bd9aaeeb6ffcee9796ca88c5`。PR #9 patchの適用だけでは、標準tarへ欠落しているSoC supportを補えない。
- 既存private build tree `/home/masataka/private/cunit-80211s-build-20261115/kernel-src` は`6.18.63-debian-t6-proto2`を名乗り、MT6990 sourceと`CONFIG_MAC80211_MESH=y`を含む。`.config` SHAは`1f70c927ea9ae20ec711506b6d63c9037d577c18b44c7e003ffe1a1cacd389b0`、既存Image/moduleのSHAは上記receiptと一致した。しかし`.git`、完全な入力manifest、ソース由来を証明する署名済みreceiptがなく、commit SHAとの対応は確認不能。
- 標準tarを使った再現ビルドを試みたが、`olddefconfig`でMT6990固有configが失われるため中止した。生成物は完成せず、candidateとして使用していない。deviceにはアクセスしていない。
- 既存テストを再実行：`python3 -m unittest discover -s tests -v` 2/2 PASS、compileall PASS、hwsim smoke PASS（SAE-configured 2-node peer、双方向ping、2437 MHz）、shell syntax PASS、`git diff --check` PASS。これは物理MT7996/MT7990、3-node HWMP、実機kernel provenanceを証明しない。
- Build provenance blockerを解消するには、PR #9と同じvendor kernel sourceの完全なtar/commitと、PR #9 patch series・config・toolchainを結びつけるinput receiptが必要。これが揃うまではPR #11の次段階であるP25製造・署名・実機bootを行わない。

## 2026-11-16: source replay / 3-node implementation (host-only, unverified)

- Added [offline source replay and optional arm64 build gate](../../scripts/replay_80211s_kernel_source.py), with input inventory tests. This can only PASS if a complete legitimate vendor/board patch series plus PR #9 reconstruct the exact private tree; the missing series is **not** reconstructed or certified by this change.
- Added [wmediumd-isolated 3-node SAE/HWMP test](../../scripts/run_80211s_hwsim_3node.sh). It enforces A-B-C only, checks no A-C direct peer, both HWMP next-hop directions through B, intermediate-node shutdown/recovery, and ping loss/latency. The test is **not yet executed**; neither 3-node PASS nor independent AMPE frame protection can be claimed.
- Added [runbook and C-unit acceptance gates](CUNIT-80211S-REPLAY-HWSIM3-20261116.ja.md) and branch-scoped host static/unit CI.
- Source provenance is still **BLOCKED** pending a complete patch manifest and verified independent rebuild. No P25 packaging/signing, C-unit write, RF test, or reboot occurred in this change.

## 2026-11-16: 3ノード実通信の独立実行と再現入力補助

- [実行run 43784875228](https://github.com/Karin-Laboratory/Debian13-Terminal6/actions/runs/43784875228) は使い捨てUbuntuホストでmac80211_hwsim/wmediumdを実行。A-B、B-C peering成立、A-C直接peerなし、A↔C ping成功、両方向HWMPのnext hop=B、B down後A-C疎通なしを確認した。
- **B up後の復旧は FAIL**。ログは「FAIL: no A-C recovery through B」。このrunのGitHub Actions表示は当初SUCCESSだったが、検証スクリプトの終了コードをteeが隠した不具合による**偽陽性**である。run全体をPASSと扱わない。
- 修正workflowではpipefailと合格マーカー照合を適用。B復帰は自動再収束とwpa_cliによる補助復旧を区別する。改修版の合否は実際のrun結果が出るまで未確定とする。
- [private source再構成補助](../../scripts/reconstruct_80211s_vendor_patch.py)を実装。Linux stable tarとprivate snapshotからvendor差分を抽出し、PR #9を最後に再適用したsource inventory一致を検査。**現時点は模擬ソースでのテストのみPASS**、実際のMT6990 treeでは未実行。
- Source provenanceの参考として[PR #1](https://github.com/Karin-Laboratory/Debian13-Terminal6/pull/1)の6.18.44→6.18.63 stable mergeとprivate保持ソースの既存証拠を特定。ただし起源/再配布権限・正確な新ソース再現・ARM64独立ビルドは引き続き未合格。
- PR #11の単体テストは9件PASS。C号機、A号機、P25、6GHz電波への操作は行っていない。

## 参照

- [PR #6: C-unit Wi-Fi 7/6GHz audit](https://github.com/Karin-Laboratory/Debian13-Terminal6/pull/6)
- [PR #9: MT7996 EEPROM/OTP initialization and C-unit Wi-Fi tests](https://github.com/Karin-Laboratory/Debian13-Terminal6/pull/9)
- [Linux mac80211 mesh Kconfig](https://github.com/torvalds/linux/blob/v6.18/net/mac80211/Kconfig)
- [Linux cfg80211/mac80211 documentation](https://docs.kernel.org/driver-api/80211/index.html)
- [wpa_supplicant mesh configuration reference](https://w1.fi/cgit/hostap/plain/wpa_supplicant/wpa_supplicant.conf)
