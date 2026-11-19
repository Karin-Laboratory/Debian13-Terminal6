# C号機ハードウェア棚卸し・機能状態更新（2026-11-19）

## 判定範囲

これは2026-11-14の詳細な読み取り棚卸し、11-19のKVM成功版復元試験、既存Draft PRの追加証拠を、2026-11-19のC号機ライブ収集で更新する資料である。今回のC号機確認は稼働中のslot Aで行った読み取り専用のスナップショットであり、再起動、slot/boot control変更、P25/P26/GPT書込み、P44内容変更、モジュールロード、RF送信は行っていない。

raspi4の管理Wi-FiからSSHは復旧していたが、最初は直結EthernetのIPが未設定でC号機に入れなかった。所有者がC号機ON・配線接続済みと確認後、既存`cunit-direct`接続が自動的にeth0へ`192.168.3.71/24`を設定し、carrierが復帰した。C号機を別経路で探索せず、厳格なknown_hosts設定と既存鍵で管理Ethernet越しに接続した。

raspi4の短時間SSH応答試験は22:42 JSTに20/20 banner、中央値60.4ms、最大91.0ms。現在root filesystemは約96%使用・約1.2GiB空きで、非公開実機バックアップ保存領域は約20GiB。別SSH sessionがprivate全体を再帰的にSHA-256走査し約3分で約7.7GBを読み出していたため、その該当プロセスツリーのみSIGTERMで停止した。保存ファイルは削除していない。Wi-Fi powersave offとpersistent journal設定は再起動後にも確認した。

ライブcollector JSONはraspi4の非公開領域に511,517 bytesで保存、SHA-256 `240206698603066436cd5e056e94de187775d623bda2681186f524a02a23cf3f`、観測時刻 `2026-11-19T13:55:02Z`。P44には保存していない。初回collector試行でMMCカード欄が空だったため、実機sysfs名が`mmc0/mmc0:0001`であることを確認し、collector globを修正して再採取した。初回の不完全な出力は正本として使っていない。

基準となるP25/P44復元、slot AのDebian起動、LAN/SSH、eMMC、KVM/OpenWrtゲストの実測は、所有者の2026-11-19実機作業記録にある。再起動後に機能ごとの列挙を全て取り直したものではない。P25は書込み後に変更せず、Aの恒久成功フラグは立てず、純正Bの成功状態を保持したと記録されている。

## 機能台帳

状態語は各証拠が示す範囲に限る。`HISTORICAL`は過去に実機で測定済みだが今回の起動では未再確認、`NOT_TESTED`は今回未試験、`UNKNOWN`は物理搭載も含め未確定を表す。

| 機能 | 最新の確認できる証拠 | 現時点の判定 | 実用化に向けた次の安全な作業 |
|---|---|---|---|
| 起動・Debian/P44 | 11-19 22:55 JST: hostname `terminal6-debian`、Debian 13.7、`6.18.63-debian-t6-proto2`、`bootslot=a`、root `/dev/mmcblk0p44` ext4 rw | PASS（採取時） | Aはtrialの可能性があるためboot controlを変更しない。今後の起動操作前に読み取り確認 |
| CPU / Cortex-A55 | 11-19 live: CPU0–3 online、AArch64/Cortex-A55。`/sys/devices/system/cpu/cpufreq`にpolicyなし | PASS（4 core online）; cpufreq API NOT_EXPOSED | P25 Kconfig・DT・cpufreq driver/providerの差分調査。動作周波数を推測しない |
| RAM / reserved memory | 11-19 live: MemTotal 1,757,888kB、MemAvailable約1.58GB、swapなし。11-14 DTに2GiB/reserved-memory | PASS（RAM読み取り） | DT reserved領域の用途を既存資料と対応づける。予約領域を合算・変更しない |
| 割り込み / DMA / IOMMU | 11-14: GICv3、arch_timer/通信IRQ観測。IOMMU_SUPPORTなし | HISTORICAL/PARTIAL | IRQ差分とIOMMU groupを読み取り採取。DMA/MMIOの直接操作はしない |
| clocks / power / reset | 11-14: MT6990 clock、scpsys、syscon reset driver bound | HISTORICAL/DRIVER_LOADED | 登録・consumer関係のみ再採取。rate、power domain、reset状態を変更しない |
| thermal / hwmon | 11-19 live: 13 thermal zones enabled、観測値約47.7–55.9°C。hwmon classなし | PASS（読み取りAPI）; physical sensor mapping PARTIAL | zone typeの用途を台帳と照合。負荷試験やfan制御はしない |
| watchdog | 11-19 live: `mtk-wdt`、inactive、timeout 31。デバイスをopenせず | PASS（driver/API認識）; watchdog機能動作NOT_TESTED | sysfs読み取りのみ。`/dev/watchdog*`をopenしない |
| eMMC / CQE / HS400 | 11-19 live: `cmdq_en=0`、HS400/8-bit/1.8V、host clock 100MHz / actual 94,999,965Hz。EXT_CSD lifetime raw `0x01 0x01`, pre-EOL `0x01`。debugfs err_stats全項目0、dmesgに現起動のMMC/ext4 I/O errorなし | PASS（読み取り状態）; 耐久年数は未推定 | 11-15の15回direct-I/O試験PASS記録を参照。長期信頼性を主張せず、新規write stressは別判断 |
| A/B boot control | 11-19: A running, `success=0`; B `success=1`。恒久成功更新なし | A trial / B recovery PASS状態 | 次回の電源操作前にmisc/bootctrlをread-onlyで再確認。自動フェイルオーバーを推定しない |
| Ethernet / MT7531 / SGMII | 11-19 live: `eth1` carrier up 2.5Gbps、`lan2` 1Gbps/full。C→raspi4、raspi4→C ping各3/3。Strict SSH login PASS。RX/TX errors 0、lan2 tx_dropped 16。今回のdmesgにTX watchdogなし | PASS（双方向IP/SSH、採取時）; 初回boot時TX watchdog原因未特定 | management path維持のままlink state/statisticsを読み取る。再起動による再現試験は別承認 |
| LAN外部ポート全体 | 11-14: PHY 0–4とDSA lan1–lan5。実コネクタ対応は一部未確認 | PORT MAP PARTIAL | 既存の所有者確認済み配線でlink stateのみ調査。抜差しは今回未実施 |
| PCIe | 11-19 live: PCIe host port `11280000` probe PASS、`11290000`はlink down / `-110`。PCI enumerationに2 network endpoint (`14c3:7990`, `14c3:7991`)が見えるが両方unbound | PARTIAL/FAIL（2番目host port probe timeout、endpoint driver未結合） | P25 source/DT/PHY rail-reset差分と既存UARTログを照合。reprobe/resetやDT変更はしない |
| Wi-Fi 2.4/5/6GHz | 11-19 live: PCIで802.11be相当の2 endpointを認識するがdriver unbound、`iw phy`なし。P44にmt76 module filesあり。一方running kernel configは`CONFIG_CFG80211` not set | PCI detection PASS; PHY/firmware/STA/AP NOT_AVAILABLE。この状態でmodule load不可 | cfg80211/mac80211を含む新P25とfirmware/EEPROMの対応が必要。RF試験は認証/regdbを満たす場合のみ。6GHz送信しない |
| MLO / EasyMesh / 802.11s | 既存PR #13にhwsim/host側試験とハードウェア未達が区別されている | C号機実通信NOT_TESTED/BLOCKED | 能力広告でなく実peer、link counter、IEEE 1905データの条件が揃うまで送信・設定変更しない |
| ESP32-C3 / UART1 / ESP-AT | 11-14にAT query、PR #5にBLE peer GATT試験記録 | HISTORICAL PASS（機能別）; 11-19起動では未再確認 | UART所有者/プロセス確認後、既存allowlistのread-only ATだけを個別実施。GPIO reset、scan、無線送信なし |
| Linux Bluetooth HCI | 11-19 live: `CONFIG_BT` not set、`/sys/class/bluetooth`なし。UART1 `/dev/ttyS1`は存在し当時fd ownerなし。既存ESP32 AT/BLE結果は別kernel/試験 | BLOCKED（標準HCI stack/transportなし）; historical ESP32 AT separate | 新P25 BT stackかESP32 HCI transportが必要。RF動作は規制・認証条件確認後 |
| GNSS | 11-19 live: `CONFIG_GNSS` not set、GNSS classなし。PR #8のconninfra/secure firmware依存未解決 | BLOCKED | kernel featureとfirmware/conninfra依存の設計・ビルドが必要。MMIO/firmware送信なし |
| WWAN / LTE / 5G | 11-19 live: CCCI/DPMAIF provider bound、`ccmni0..20` 21 interfacesは全DOWN、通信sessionなし | transport API exposed; data path NOT_TESTED | modem service/transportを読み取り確認。SIM/IMEI等は記録・公開しない。推測AT/QMI送信なし |
| USB host/device | 11-19 live: `CONFIG_USB=m`, `CONFIG_USB_XHCI_HCD=m`、USB bus/class empty、matching USB modules absent from current `/lib/modules`. PR #7は別時点volatile root hubs | Current USB NOT_AVAILABLE; historic controller registration separate | matching modulesを用いた試験はP44 backup/ABI確認後。USB VBUSと接続機器を確かめずcontrollerをstartしない |
| GPIO / pinctrl | 11-19 live: `mt69xx-pinctrl` bound、236 GPIO lines公開 | PASS（chip/API enumeration）; individual wiring/function PARTIAL | line ownershipだけ読む。GPIO request/output/reset toggleをしない |
| I2C | 11-19 live: `CONFIG_I2C=y`だが`/sys/bus/i2c/devices`にadapter/deviceなし | NOT_REGISTERED | controller DT/driver/provider dependencyを調べる。bus scanしない |
| SPI | 11-19 live: `CONFIG_SPI=y`だが`/sys/bus/spi/devices` empty | NOT_REGISTERED | controller DT/driver依存を調べる。未知device probe/CS操作をしない |
| PWM / fan | 11-19 live: `CONFIG_PWM=y`だがpwm class empty。PR #7は7-channel provider/pwm-fanの一時試験 | Current NOT_REGISTERED; historical volatile PASS separate | provider ABI/source確認後、fan dutyの初期安全値を確認。変更しない |
| LEDs / buttons | 11-19 live: LED/input class empty。11-14はDT候補、button event未確認 | NOT_REGISTERED/UNKNOWN | DT compatibleと物理部品の対応を確認。brightness書込み・button操作不要 |
| RTC | 11-19 live: `CONFIG_RTC_CLASS=y`、RTC class empty | NOT_DETECTED | DT候補とdriver/provider bindingを照合。搭載を断定しない |
| TRNG / crypto | 11-19 live: `CONFIG_HW_RANDOM=y`, `rng_current=none`, `rng_available=none`; `getrandom`はsoftware API | Hardware RNG NOT_REGISTERED | controller driver/providerを調べる。entropy/MMIO操作しない |
| KVM / QEMU | 11-19 live: `CONFIG_KVM=y`, `/dev/kvm` present, QEMU 10.0.13。OpenWrt ARM64 guest Linux 6.12.112/procd起動。今回さらに256MiB/1 vCPU、virtio-net、QEMU user network `restrict=on`でDHCP `10.0.2.15`、gateway `10.0.2.2` ping 2/2 PASS | PASS（KVM guest起動、限定user-network DHCP/gateway通信）; guest↔host/external network NOT_TESTED | 既存基準維持。制限付きuser networking以外の接続は試験しない |
| GPU / audio / multimedia / sensors | 11-14 DT上に候補記述、実装・部品対応は不明 | UNKNOWN | DT compatibleとplatform bindを照合し、搭載を断定しない |

## 2026-11-19ライブ状態の補足

- **Ethernetと管理アクセス:** raspi4→C、C→raspi4の各pingは3/3成功。既知host keyを検証するSSH鍵認証でCへログイン成功。C `eth1`はcarrier up 2.5Gbps、switch port `lan2`は1Gbps/full。エラー0、`lan2` TX dropped 16。今回のdmesg検索では`NETDEV WATCHDOG`、MMC I/O error、ext4 errorは見つからなかった。これは今回の稼働期間に限る。
- **eMMC/P44:** `bootslot=a`、`/dev/mmcblk0p44` ext4を`/`へrw mount。HS400、8-bit、1.8V、requested 100MHz/actual 94,999,965Hz、CQE off。debugfs `err_stats`全項目0。EXT_CSD寿命バイトは意味を拡張解釈せずraw値で保全。
- **PCIe/Wi-Fi:** PCIe config spaceでMT7990系endpoint 2個を列挙するが、mt76ドライバはどちらにも結合していない。P44にはmt76系module fileがあるが、稼働kernelは`CONFIG_CFG80211` not set。`modprobe -n mt7996e`もmodule indexから見つけられず失敗。実機にロードせず、PHY/API/RFのPASSにはしていない。`CONFIG_BT`、`CONFIG_GNSS`も無効。
- **USB:** `CONFIG_USB=m`/`CONFIG_USB_XHCI_HCD=m`だが、現P44のkernel module treeにUSB/xHCI moduleがなく、USB bus/classも未登録。PR #7の別時点volatile root hub試験を今回のPASSに流用しない。USB接続機器/VBUSの状態が分からないためhost controllerを起動していない。
- **周辺API:** 13 thermal zones、mtk-wdt inactive、236 GPIO linesは列挙。CPU0–3 online。cpufreq policy、RTC、PWM、LED、input、GNSS、Bluetooth class、USB class、I2C/SPI adapter、hardware RNG sourceは現起動で公開されない。netdevの`ccmni0..20`は全DOWN、WAN data sessionなし。
- **既存基準と追加試験:** `/dev/kvm` present、`CONFIG_KVM=y`、QEMU 10.0.13。今回、RAM上のOpenWrt 25.12.6 ARM64 initramfs kernel 6.12.112を256MiB/1 vCPUでKVM起動し、Linux/procdを確認。virtio-netを追加しQEMU user networkを`restrict=on`で起動、ゲスト内のeth0でDHCP lease `10.0.2.15/24`（server `10.0.2.2`）を取得、`10.0.2.2`へ2/2 ping成功。ゲストのeth0は一時的にbridgeから外しDHCPを行っただけで、ゲストinitramfsとホストP44には設定を保存していない。restrictモードのため外部・実LAN・ホスト間通信はNOT_TESTED。QEMU停止後にC号機Debianと管理SSHが継続していることを確認。元ログはC号機tmpfsの`/run/kvm-acceptance/restricted-net-console.log`（17,660 bytes、SHA-256 `a86af1725f1edd4ebffd8f3a535b1487096f0bc593d59c333ee91529a663dae1`）にあり、同サイズ・同SHAのコピーをraspi4の非公開領域へ保全した。公開記録には保存先パスを記載しない。P44へはコピーしていない。

DTには881 nodes/433 compatible propertiesがあり、platform busには335 device entries中40 driver linksがあった。残りのDT/platform entryは共通SoC・syscon・power/clock blocksや無効/未使用定義を含むため、未bind件数だけで未実装部品や物理搭載を結論づけない。

## 今回追加した実装

[`scripts/collect-terminal6-hardware.py`](../../scripts/collect-terminal6-hardware.py) の空だった`sysfs`欄を実装した。CPU frequency policy、MMC寿命/モード属性、block size、netdev link/statistics、thermal/hwmon、LED、input、PWM、RTC、watchdog、RNG、USB ID、GPIO chipのallowlist読み取りを追加。MAC address、MMC CID/serial、USB serial、EEPROM/calibration、任意ueventはこの新しいsysfs欄に含めない。

collector全体のDevice Tree/bus/proc出力は従来通り**privateのままレビューする**。この変更は対象機器を操作せず、GPIO、watchdog、bus scan、module load、radio activationも行わない。合成sysfs treeを用いた秘匿フィールド除外・各属性取得テストはPASS。これはhost-side testであり、C号機での新collector実行結果ではない。

## raspi4ゲートウェイ診断（2026-11-19 22:42 JST）

C号機への実機経路を確立できなかったため、管理ゲートウェイだけを読み取り診断した。

| 項目 | 実測 | 評価 |
|---|---|---|
| raspi4 SSH | 再起動後、SSH service active。SSH banner TCP試験20/20、中央値60.4ms/最大91.0ms | 今回の短時間試験PASS。長期安定性は未確認 |
| Wi-Fi | 接続済み、5GHz/5180MHz、信号-61dBm。Wi-Fi powersaveは再起動後もoff | 今回観測では接続安定。電波品質を長期評価したものではない |
| 直結Ethernet | `eth0` `NO-CARRIER`; static direct profileは存在するがIP未設定 | C号機との物理リンク不成立。対象側電源・ケーブル・ポートは未特定 |
| UART | CH340 `/dev/ttyUSB0` を含むserial deviceなし | 今回はUART採取不可 |
| CPU/RAM/thermal | 十分なRAM。`vcgencmd get_throttled=0x0`。現行boot kernel logにMMC/ext4 I/O errorなし | 今回の読み取り時点で明白な熱/電源/eMMC異常なし |
| root filesystem | 29GiB中約27GiB使用、96%、約1.2GiB空き。private保存領域約20GiB | 容量余裕は小さい。保持対象バックアップは削除せず |
| 実行中の走査 | 追加SSH sessionがprivate全体の`find | sort | sha256sum`を実行中。3分弱で約7.7GBを読み、sha256sumが約40% CPU、MMC waitでD-state | 全バックアップ再ハッシュは今回不要で、反復負荷にもなるため、該当PIDのプロセスツリーだけSIGTERMで停止。データは変更していない |
| WireGuard起動 | `wg-quick@wg0`はfailed。起動ログはendpoint routeを`via 192.168.0.1 dev eth0 src 192.168.0.89`へ追加しようとして`Nexthop has invalid gateway`。実際のdefault routeはWi-Fi | staleなEthernet前提設定の可能性。VPN用途・意図が未確認のため設定変更せず。SSH遅延との因果は未確定 |

読み取り前に稼働していたprivate全体ハッシュ処理は、対象と必要性を確認できず、かつバックアップ大容量ファイルの不要な全量再読込だったため停止した。APT cacheは以前のraspi4診断で`apt-get clean`済み。journaldは16MiBに制限されたpersistent設定、Wi-Fi powersave off設定を既存変更として再起動後に確認した。privateバックアップや作業成果物の削除、ネットワーク経路の変更は行っていない。

## 既存成果との関係

- 2026-11-14の詳細棚卸しと証拠境界：[総合インベントリ](CUNIT-INVENTORY-API-20261114.ja.md)、[詳細](CUNIT-DEVICE-DETAILS-20261114.ja.md)、[無線](CUNIT-RADIOS-20261114.ja.md)、[OpenWrt差分](CUNIT-OPENWRT-DELTA-20261114.ja.md)
- PR [#7 hardware ledger](https://github.com/Karin-Laboratory/Debian13-Terminal6/pull/7) はDraft。PWM/USB等の追加はvolatile実機試験であり、この起動への永続化を意味しない。
- PR [#3 eMMC試験](https://github.com/Karin-Laboratory/Debian13-Terminal6/pull/3) は100MHz/no-CQEの指定試験負荷PASSを記録。長期信頼性の証明ではない。
- PR [#5 ESP32-C3 BLE](https://github.com/Karin-Laboratory/Debian13-Terminal6/pull/5)、[#6 Wi-Fi/regdb](https://github.com/Karin-Laboratory/Debian13-Terminal6/pull/6)、[#8 GNSS](https://github.com/Karin-Laboratory/Debian13-Terminal6/pull/8)、[#9 Wi-Fi実通信](https://github.com/Karin-Laboratory/Debian13-Terminal6/pull/9)、[#13 Wi-Fi integration](https://github.com/Karin-Laboratory/Debian13-Terminal6/pull/13) の状態をこの補足で上書きしない。
- PR [#32–#35 earlyboot/MMC修正候補](https://github.com/Karin-Laboratory/Debian13-Terminal6/pull/35) はDraft/source build evidence。成功版P25を実機で再試験した事実ではない。

## 再接続後の読み取り確認（2026-11-19 23:06 JST）

所有者からraspi4再起動後にSSHが復旧したとの連絡を受け、既存の管理経路からC号機を読み取り確認した。raspi4のSSH対話シェルを再利用し、C号機へは既知host keyを`StrictHostKeyChecking=yes`で検証して接続した。

- C号機は`terminal6-debian`、kernel `6.18.63-debian-t6-proto2`、`bootslot=a`、uptime約4時間50分。P25、boot control、P44、slot、ネットワーク設定の変更や再起動は行っていない。
- 今回の`/proc/cmdline`とchosen bootargsには`root=/dev/mmcblk0p26`（`rootfs_a`、squashfs）が記載される一方、`findmnt /`は`/dev/mmcblk0p44`（`rootfs_data`、ext4、rw）を返し、`lsblk`もp44を`/`として表示した。initramfs/preinit後のroot引継ぎを含む構成と考えられるが、遷移機構は今回解析していない。したがって「カーネル起動引数のroot」と「現在の実root mount」を区別して記録し、旧表の短い表現は実root mountを指すものとする。
- 今回の起動中、`/sys/kernel/debug/mmc0/err_stats`は全カウンタ0。dmesgの限定検索では起動時watchdog初期化以外にMMC/ext4 I/O error、timeout、NETDEV watchdogは見つからなかった。限定検索であるため、全ログに異常がないとの保証ではない。
- 読み取り時点で`eth1`/`lan2`がUP、`lan2`に`192.168.3.1/24`。CPU/GPU/音声/メディア/電源/devfreq classは空。`lsmod`は既存の`test24_path_probe`、`test23_mdio_switch`、`test23_netsys_fixedlink`のみで、既存モジュールをアンロードしていない。
- raspi4からCへのStrict SSH再接続に成功。既存の起動実績は維持。今回も新たに有効化した機能はない。

本節はライブ差分の追記であり、前節の時刻・collector値は過去の採取結果として維持する。個体固有UUID、MAC、シリアルは公開記録へ含めていない。

## 次回の優先順位

1. C号機を電源ONと確認し、raspi4 `eth0`直結リンクまたはUART USB接続を復旧後、strict SSH/UARTでhostname/kernel/cmdline/slot/root/mountを読み取り確認する。A trial・B successの状態を変えない。このturnはSSHとEthernetで読み取り再確認済みだが、UART接続・取得は未確認。
2. 新collectorをSSH stdinから実行してVM側へ保存し、公開前にMAC/CID/serial/firmware/calibration等を除去する。collector出力をP44へ書かない。
3. active module、firmware、PCI/USB/I2C/SPI/GPIO/PWM、thermal/RNG/RTC、各netdevを最新kernel ABIと照合。ドライバをロードする前にP44バックアップとrollbackを確保する。
4. 既存moduleだけで行える非送信・読み取りAPI確認を優先。PWMやLEDなど出力変化を伴う試験は物理対応と安全な初期値を確認するまで変更しない。
5. radio/WWAN/GNSSは規制・対向機・専用初期化依存が揃った機能だけを試験。6GHz送信、未知ATコマンド、無線scan、SIM状態取得はこの補足では許可・実施していない。
6. P25/DTB変更・再起動を要する機能は、現在のboot controlと復旧条件を個別に確かめるまで保留する。

**この更新で新たにP44へ有効化した機能はない。** raspi4自身についてはWi-Fi省電力OFFの永続設定と有限サイズのpersistent journalを再起動後にも確認した。C号機は前節のcollector採取に加え、本節の再接続後読み取り確認および一時QEMU guest user-network試験を完了した。UARTの接続・取得は未確認のため、次回はUART実接続を確認し、現行ハードウェアとの差分を非破壊で補う。
