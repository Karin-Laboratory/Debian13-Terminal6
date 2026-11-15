# C号機 IEEE 802.11s mesh 状況 (2026-11-15)

## 現時点の判定

| 段階 | 状態 | 根拠 |
|---|---|---|
| 802.11s実装の有無 | kernel/driver sourceには実装あり | Linux 6.18.63 mac80211 mesh core、HWMP、peer-link state machine、およびmt7996 mesh関連コードを確認。 |
| 保存済みDebian kernel config | **BLOCKED: `CONFIG_MAC80211_MESH`未設定** | PR #9用の6.18.63 build inputで`CFG80211=y`, `MAC80211=y`, `MT7996E=m`だが`MAC80211_MESH`はunset。mt7996のmesh interface advertisementとmesh-specific処理は`#ifdef CONFIG_MAC80211_MESH`でガードされる。 |
| 修正config候補 | host config resolution PASS | このブランチの最小fragmentは`CONFIG_MAC80211_MESH=y`のみ。隔離したKbuild source copyで`olddefconfig`後も有効で、source guardがPASS。 |
| ARM64 kernel/module build | **PASS (isolated host build)** | Privateな隔離ソースコピーでLinux 6.18.63 `Image modules` build exit 0。ARM64 Imageとmt76/mt7996 modulesを生成。未署名・未パッケージ・未起動。 |
| hwsim 2-node mesh | **PASS (host synthetic)** | 2437MHz、wpa_supplicant SAE mesh設定、peer成立および双方向IP pingを実行。物理MT7990動作の証拠ではない。 |
| A号機 802.11s | UNKNOWN | 保存済み純正観測にはWi-Fi設定/PHY/APの情報はあるが、mesh point、peer、HWMP path、mesh dataの証拠がない。独自mesh/EasyMesh/WDS/802.11sのいずれかを推定しない。 |
| C号機 mesh peer / SAE / HWMP / IP | NOT TESTED | 実機操作を行っていない。 |
| 3-node multi-hop | NOT TESTED | 仮想試験は2ノード。実機対向ノードも限定hwsim link topologyも未検証。 |

## A号機との比較

保存済みPR #6のread-only観測では、A号機はStock Linux 5.4.238のMediaTek proprietary `mt_wifi`/MT7990構成で、別PHYの2.4/5/6GHz表示とAP設定が記録されている。一方、IEEE 802.11s mesh-point interface、peer link state、HWMP route、4-address forwardingまたは暗号化mesh trafficは記録されていない。したがってA号機が802.11sを使用するとは言えない。純正のmesh marketing/mesh controller機能が観測されても、802.11s dataplaneと同一視しない。

## C号機 source audit

参照した保存ソースはLinux stable v6.18.63 (`1cdda838e8475edf89b73ff0cc952005dd0b1fa7`) とPR #9のC号機EEPROM/OTP初期化修正入りmt76 source。

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

## 参照

- [PR #6: C-unit Wi-Fi 7/6GHz audit](https://github.com/Karin-Laboratory/Debian13-Terminal6/pull/6)
- [PR #9: MT7996 EEPROM/OTP initialization and C-unit Wi-Fi tests](https://github.com/Karin-Laboratory/Debian13-Terminal6/pull/9)
- [Linux mac80211 mesh Kconfig](https://github.com/torvalds/linux/blob/v6.18/net/mac80211/Kconfig)
- [Linux cfg80211/mac80211 documentation](https://docs.kernel.org/driver-api/80211/index.html)
- [wpa_supplicant mesh configuration reference](https://w1.fi/cgit/hostap/plain/wpa_supplicant/wpa_supplicant.conf)
