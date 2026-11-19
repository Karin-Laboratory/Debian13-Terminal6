# C号機ハードウェア棚卸し・機能状態更新（2026-11-19）

## 判定範囲

これは2026-11-14の詳細な読み取り棚卸しを、11-19のC号機KVM成功版復元試験および既存Draft PRの追加証拠で更新する補足である。**今回の実行環境からraspi4のSSH/22へ到達できず、C号機へ再接続した新規全量スキャンは未実施。** したがって「11-19にC号機上で再確認」と書いた項目以外は、過去の実機測定を最新状態とみなさない。

raspi4 `192.168.0.38` はこの実行環境の同一 `/22` 経路からTCP/22を3回試したが、タイムアウトまたは `No route to host`。SSHホスト鍵検証を無効化した接続や、許可されていないLAN機器への迂回はしていない。今回、C号機の再起動、slot/boot control変更、P25/P26/GPT書込み、RF送信は行っていない。

基準となるP25/P44復元、slot AのDebian起動、LAN/SSH、eMMC、KVM/OpenWrtゲストの実測は、所有者の2026-11-19実機作業記録にある。再起動後に機能ごとの列挙を全て取り直したものではない。P25は書込み後に変更せず、Aの恒久成功フラグは立てず、純正Bの成功状態を保持したと記録されている。

## 機能台帳

状態語は各証拠が示す範囲に限る。`HISTORICAL`は過去に実機で測定済みだが今回の起動では未再確認、`NOT_TESTED`は今回未試験、`UNKNOWN`は物理搭載も含め未確定を表す。

| 機能 | 最新の確認できる証拠 | 現時点の判定 | 実用化に向けた次の安全な作業 |
|---|---|---|---|
| 起動・Debian/P44 | 11-19: Debian 13.7、`6.18.63-debian-t6-proto2`、P44 ext4を`/`へrwマウント | PASS（その試験起動） | 次回アクセス時に読み取り専用のboot/root/mount/uptimeを再採取。Aはtrialのためboot controlを変更しない |
| CPU / Cortex-A55 | 11-14: 4 online core、AArch64。11-19: kernel/userspace起動 | HISTORICAL; 11-19全コア再列挙NOT_TESTED | 新collectorでonline CPU、cpufreq policy/governor/limitsを取得。policy不在なら現状のまま記録 |
| RAM / reserved memory | 11-14: DT 2GiB、MemTotal約1.76GiB、reserved-memoryノードあり | HISTORICAL | 最新`/proc/meminfo`、DT metadata。予約領域を合算・変更しない |
| 割り込み / DMA / IOMMU | 11-14: GICv3、arch_timer/通信IRQ観測。IOMMU_SUPPORTなし | HISTORICAL/PARTIAL | IRQ差分とIOMMU groupを読み取り採取。DMA/MMIOの直接操作はしない |
| clocks / power / reset | 11-14: MT6990 clock、scpsys、syscon reset driver bound | HISTORICAL/DRIVER_LOADED | 登録・consumer関係のみ再採取。rate、power domain、reset状態を変更しない |
| thermal / hwmon | 11-14: 13 thermal zonesが値を返した。nvmem校正警告あり | HISTORICAL/PARTIAL | zone type/tempとhwmon入力を記録。過温度を誘発する負荷試験やfan制御は行わない |
| watchdog | 11-14: `mtk-wdt`登録、inactive、timeout 31、nowayout=0 | HISTORICAL/DRIVER_LOADED | sysfsだけを読む。`/dev/watchdog*`をopenしない |
| eMMC / CQE / HS400 | 11-19: CQE無効、HS400/8-bit/1.8V、実clock 94,999,965Hz。該当起動ログでMMC/CQE/ext4 error 0 | PASS（測定時） | 11-15の15回direct-I/O試験PASS記録を参照。長期信頼性を主張せず、新規write stressは別判断 |
| A/B boot control | 11-19: A running, `success=0`; B `success=1`。恒久成功更新なし | A trial / B recovery PASS状態 | 次回の電源操作前にmisc/bootctrlをread-onlyで再確認。自動フェイルオーバーを推定しない |
| Ethernet / MT7531 / SGMII | 11-19: 電源サイクル後`lan2@eth1` UP、C↔raspi4 ping各3/3、Strict SSH PASS。初回起動時TX watchdogあり | PASS後に復帰。ただし初回異常原因未特定 | 管理経路維持のままlink state、driver、statisticsを読み取る。boot-success変更や再起動で再現試験しない |
| LAN外部ポート全体 | 11-14: PHY 0–4とDSA lan1–lan5。実コネクタ対応は一部未確認 | PORT MAP PARTIAL | 既存の所有者確認済み配線でlink stateのみ調査。抜差しは今回未実施 |
| PCIe | 11-19: PCIe link-down / probe `-110` 記録あり | FAIL/未解決（当該endpoint） | UART/dmesgおよびsysfs bindを読み取り比較。reprobe/resetやDT変更は別試験 |
| Wi-Fi 2.4/5/6GHz | 11-14/既存PR #6/#9: MT7990 PHY/driver初期化履歴と2.4/5GHz STA実通信履歴あり。11-19起動でWi-Fiは`CFG80211_NOT_BUILTIN`と記録 | HISTORICAL; 現在のPHY/STA/APはNOT_TESTED | まずPCI/driver/firmware/regdbを読み取り。RF試験は国・認証・regdbを別途満たす場合のみ。6GHz送信はしない |
| MLO / EasyMesh / 802.11s | 既存PR #13にhwsim/host側試験とハードウェア未達が区別されている | C号機実通信NOT_TESTED/BLOCKED | 能力広告でなく実peer、link counter、IEEE 1905データの条件が揃うまで送信・設定変更しない |
| ESP32-C3 / UART1 / ESP-AT | 11-14にAT query、PR #5にBLE peer GATT試験記録 | HISTORICAL PASS（機能別）; 11-19起動では未再確認 | UART所有者/プロセス確認後、既存allowlistのread-only ATだけを個別実施。GPIO reset、scan、無線送信なし |
| Linux Bluetooth HCI | 11-14: CONFIG_BT/HCI transportなし。ESP32 AT companionとは別経路 | BLOCKED（標準HCI） | 新kernel/P44でBT stack/transportがあるか読み取り、存在しなければ必要な同一ABI module/sourceを検討 |
| GNSS | PR #8/11-14: driver未結合、conninfra/secure firmware依存未解決 | BLOCKED | MMIO/firmware送信なしで依存関係と上流driver ABIを調査 |
| WWAN / LTE / 5G | 11-14: CCCI/CCMNI列挙。DebianでSIM/PDN/IP未検証。別OS Stage10実績あり | Debian data path NOT_TESTED | modem service/transportを読み取り確認。SIM/IMEI等は記録・公開しない。推測AT/QMI送信なし |
| USB host/device | PR #7: matching volatile modulesでUSB2/USB3 root hubs登録。外付けperipheral/VBUS未試験 | HISTORICAL controller registration only; current boot NOT_TESTED | module ABI・host controller・root hubを読み取り確認。周辺機器/VBUS/role switchを触らない |
| GPIO / pinctrl | 11-14: MT69xx pinctrl、236 linesをgpiodで列挙。特定consumer記録あり | HISTORICAL registration | line ownershipだけ読む。GPIO request/output/reset toggleをしない |
| I2C | 11-14: controller DT/driver候補、adapter未登録 | BLOCKED/HISTORICAL | `/sys/bus/i2c/devices`とdriver/provider dependenciesを読み取り。bus scanしない |
| SPI | 11-14: controller DT/driver登録候補、SPI childなし | BLOCKED/HISTORICAL | `/sys/bus/spi/devices`確認。未知デバイスprobeやCS操作をしない |
| PWM / fan | PR #7: 7-channel providerとpwm-fan bind、channel 4 max-duty報告。物理回転未確認、試験moduleはvolatile | HISTORICAL temporary PASS; current boot NOT_TESTED | 現在のprovider/moduleを確認し、初回は読み取りのみ。duty変更はしない |
| LEDs / buttons | 11-14: `mt76-phy0` LED以外はDT候補、button event未確認 | PARTIAL/UNKNOWN | LED classとinput deviceを読み取る。brightness書込み、実ボタン要求は今回未実施 |
| RTC | 11-14: RTC classなし、DT候補のみ | NOT_DETECTED（当時） | `/sys/class/rtc`を再確認。DT記述だけで搭載判定しない |
| TRNG / crypto | 11-14: hwrng sourceなし、EIP97未結合。`getrandom`成功はsoftware API | BLOCKED/HISTORICAL | `rng_current`, `/proc/crypto`, kernel configの読み取り。entropy推測やMMIOはしない |
| KVM / QEMU | 11-19: CONFIG_KVM=y、VHE、`/dev/kvm`、KVM enabled。OpenWrt ARM64 guest Linux 6.12.112とprocd起動 | PASS（実機、guest network除く） | 既存PASSを再起動なしに維持。guest networkは次の独立検証、ホスト接続影響を隔離 |
| GPU / audio / multimedia / sensors | 11-14 DT上に候補記述、実装・部品対応は不明 | UNKNOWN | DT compatibleとplatform bindを照合し、搭載を断定しない |

## 今回追加した実装

[`scripts/collect-terminal6-hardware.py`](../../scripts/collect-terminal6-hardware.py) の空だった`sysfs`欄を実装した。CPU frequency policy、MMC寿命/モード属性、block size、netdev link/statistics、thermal/hwmon、LED、input、PWM、RTC、watchdog、RNG、USB ID、GPIO chipのallowlist読み取りを追加。MAC address、MMC CID/serial、USB serial、EEPROM/calibration、任意ueventはこの新しいsysfs欄に含めない。

collector全体のDevice Tree/bus/proc出力は従来通り**privateのままレビューする**。この変更は対象機器を操作せず、GPIO、watchdog、bus scan、module load、radio activationも行わない。合成sysfs treeを用いた秘匿フィールド除外・各属性取得テストはPASS。これはhost-side testであり、C号機での新collector実行結果ではない。

## 既存成果との関係

- 2026-11-14の詳細棚卸しと証拠境界：[総合インベントリ](CUNIT-INVENTORY-API-20261114.ja.md)、[詳細](CUNIT-DEVICE-DETAILS-20261114.ja.md)、[無線](CUNIT-RADIOS-20261114.ja.md)、[OpenWrt差分](CUNIT-OPENWRT-DELTA-20261114.ja.md)
- PR [#7 hardware ledger](https://github.com/Karin-Laboratory/Debian13-Terminal6/pull/7) はDraft。PWM/USB等の追加はvolatile実機試験であり、この起動への永続化を意味しない。
- PR [#3 eMMC試験](https://github.com/Karin-Laboratory/Debian13-Terminal6/pull/3) は100MHz/no-CQEの指定試験負荷PASSを記録。長期信頼性の証明ではない。
- PR [#5 ESP32-C3 BLE](https://github.com/Karin-Laboratory/Debian13-Terminal6/pull/5)、[#6 Wi-Fi/regdb](https://github.com/Karin-Laboratory/Debian13-Terminal6/pull/6)、[#8 GNSS](https://github.com/Karin-Laboratory/Debian13-Terminal6/pull/8)、[#9 Wi-Fi実通信](https://github.com/Karin-Laboratory/Debian13-Terminal6/pull/9)、[#13 Wi-Fi integration](https://github.com/Karin-Laboratory/Debian13-Terminal6/pull/13) の状態をこの補足で上書きしない。
- PR [#32–#35 earlyboot/MMC修正候補](https://github.com/Karin-Laboratory/Debian13-Terminal6/pull/35) はDraft/source build evidence。成功版P25を実機で再試験した事実ではない。

## 次回の優先順位

1. raspi4経由のstrict SSHとUARTを復旧し、C号機のhostname/kernel/cmdline/slot/root/mountを読み取り確認する。A trial・B successの状態を変えない。
2. 新collectorをSSH stdinから実行してVM側へ保存し、公開前にMAC/CID/serial/firmware/calibration等を除去する。collector出力をP44へ書かない。
3. active module、firmware、PCI/USB/I2C/SPI/GPIO/PWM、thermal/RNG/RTC、各netdevを最新kernel ABIと照合。ドライバをロードする前にP44バックアップとrollbackを確保する。
4. 既存moduleだけで行える非送信・読み取りAPI確認を優先。PWMやLEDなど出力変化を伴う試験は物理対応と安全な初期値を確認するまで変更しない。
5. radio/WWAN/GNSSは規制・対向機・専用初期化依存が揃った機能だけを試験。6GHz送信、未知ATコマンド、無線scan、SIM状態取得はこの補足では許可・実施していない。
6. P25/DTB変更・再起動を要する機能は、現在のboot controlと復旧条件を個別に確かめるまで保留する。

**この更新で新たにP44へ有効化した機能はない。** 実機到達性が回復した後、上記の非破壊再採取から再開する。
