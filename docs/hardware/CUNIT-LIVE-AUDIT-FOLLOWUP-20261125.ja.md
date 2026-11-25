# C号機Debian 13 UART監査・第2段階の原因分析と次期ビルド台帳

作業日: 2026-11-25 JST  
対象: 既存C号機、slot A、Debian 13.8、`6.18.63-debian-t6-proto2`  
先行記録: [C号機 Debian 13 UART実機監査](CUNIT-LIVE-AUDIT-20261125.ja.md)

## 結論

この起動ではDebianとP44、eMMCの限定スナップショット、UART、USB root hub、PCIe列挙、KVM APIが確認できた。一方、管理LANの障害点は「外部LAN2のlink」より後、スイッチからCPU側MACへ渡る経路に絞られた。LAN2の受信カウンタは増えたが、送信・CPU側`eth1`受信・`br-lan`受信は増えていない。起動時の既存管理サービスは失敗した。サービススクリプトには条件成立時に`phy_init`を書込み許可付きで呼ぶ分岐があるが、保存journalからその分岐が実際に実行されたとは確認できない。journalの一般的な`phy_init` initcall行は、このmodule parameter呼出しの証拠ではない。本監査ではその初期化を実行していない。

Wi-Fiについては、ドライバと依存モジュールのファイルは揃うが、起動サービスが必要な4 firmwareを確保できず、モジュール挿入より前に停止する。よって現在のPCI driver未bindを別個のprobe不具合とはまだ認定できない。I2C、SPI、PWM、RTC、GNSSも、実行中ノードの`compatible`と利用カーネルのdriver match tableが合わない、または必要な専用実装がないという具体的なビルド側不足が確認できた。次期ビルドではsource/DTS/firmware供給条件を先に整え、安易なcompatible置換や未知のハードウェア操作を避ける。

## 証拠範囲・保管状態

前回のprivate evidence bundleには、kernel `dmesg`、systemd journal、実kernel config、選択config、runtime FDT/DTS、MMC ios/error、module metadata、`modules.dep`/`modules.alias`、network関連unit・script、clock/regulator/pinctrl/interrupt snapshot等がある。ファイルごとのサイズ・SHA-256はprivate `EVIDENCE-MANIFEST-20261125.txt`に記録した。runtime FDT/DTS、raw journal/dmesg、EEPROM/OTP等は個体情報を含み得るため公開Gitへ置かない。

| 資料 | 状態 | 制約 |
|---|---|---|
| `/sys/firmware/fdt` 実体 | private bundle保存済み、177,338 bytes、SHA-256 `54ff2e7a08ba2fb45360b64862e6fcd3cdf05de13c8ec4488dbd7e0d6b5a0161` | 公開しない。個体固有rawdata/予約情報を含む |
| runtime config | `/proc/config.gz`相当をprivate保存、SHA-256 `257cceb4ade92ada2c3f822ab34d75e845d67f610a9f3ea89716044b8a0e6d3c` | 公開版には選択項目のみを転記 |
| dmesg / journal / sysfs snapshots | private bundle内、各hashはprivate manifest | journalの誤った端末時計を実時刻として扱わない |
| 生UART byte stream | **NOT_SAVED** | 電気的な生バイト列は取得していない。短い読み取り専用コマンド応答をプロンプト境界で保存したツールレベルtranscriptはprivate `uart-readonly-verified-followup-20261125.txt`（4,834 bytes、SHA-256 `262e058f5595c3001a3dded13aff6c7d9348df914ccd1287159550f0c7029ed6`）。端末echoには折返しがあり、生UARTの代替ではない |
| UART追補スナップショット | private `uart-readonly-runtime-supplement-20261125.txt`（4,063 bytes、SHA-256 `91f20c042c2e3c53bf67eec83c44a3e4094d8dabf638bc1e3d79778f04f94ac9`） | 現在のFDT/config hash、platform driver bindings、loaded module名、MMC error stats、thermal/cooling、Wi-Fi module hashとfirmware filename presenceの読み取り結果。raw wire captureではない |
| platform-device/driver全対応表 | **PARTIAL** | private `platform-drivers.txt`は0 bytes。全device binding一覧として不完全 |
| 過去成功版すべてのDTB/config/firmware | **PARTIAL** | ローカルにはKVM成功版DTB等一部だけ。Wi-Fi/BLE/GNSS/LTE成功版の完全なDTB・config・個体firmwareを一括比較する資産はない |

機器時計は2026-04-13を示し、journalもその誤った機器時刻を使用している。2026-11-25は作業セッション日付であり、機器時計から復元した採取時刻ではない。raspi3への新規SSH接続は行っていない。既存UARTセッションのroot状態を維持し、保存済みhost-side証拠を追加解析した。

private保全先は `work/hardware/private/cunit-live-audit-20261125/` 以下（Git管理対象外）である。`EVIDENCE-MANIFEST-20261125.txt`（SHA-256 `a9a7dccca7fe505601d28923e8e53f340aeea4269099819b29816c8eb32d927b`）が既存bundleと追補transcriptのファイル一覧・サイズ・SHAを記録する。transcriptは逐次コマンドの返答を保存したテキスト記録であり、UART wire captureではない。

追補transcriptは`Mon Apr 13 21:01:39 UTC 2026`、uptime `5015.40 s`を示し、作業日2026-11-25とは異なる機器時計を確認した。コマンドは読み取り専用で、slot、boot-control、ファイル、module、network設定は変更していない。破損した先行transcriptは破棄しmanifestに含めていない。

より新しい短時間スナップショット（uptime `5389.48 s`）でも`/sys/firmware/fdt`と`/proc/config.gz`のSHAは既存保存物と一致した。同じDTB/configが当該起動で保持されていたことを裏付ける。platform driver列挙ではMTK clock/scpsys、UART、LVTS、USB host/device、eMMC、PCIe、watchdog、CCCIのbindを確認し、Ethernetは`test23_netsys_fixedlink`/`mtk_soc_eth`、DSAはロード済み`test23_mdio_switch`、probe moduleは`test24_path_probe`だった。thermal zoneは13個（約54.3–62.0°Cの一点読み取り）、cooling_deviceは存在せず、cpufreq directoryにpolicyはない。これは一時点の観測で、長時間の熱・負荷・安定性試験ではない。

## 追加runtime snapshot

先行文書のLAN link速度は前の採取時点の値である。追補時点では`lan2 carrier=1, 100 Mbps`、`eth1 up, 2500 Mbps`だった。`lan2`のRX=712/TX=0、`eth1` RX/TX=0/0、`br-lan` RX=0/TX=10。raspi3直結試験記録はraspi3 eth0 `192.168.1.50/24`、明示経路でARP/ping不達であり、`192.168.3.50`ではない。

これは同一時点のcounter snapshotであり、個々のARPフレームと相関したcaptureではない。`lan2` RX増分は外部portまでのingressを示唆し、CPU path仮説を強めるが、counterだけではVLAN/tag/CPU portのどれが原因か確定できない。100Mbpsと先行時点の1000Mbpsの差も、相手側link条件を含め原因未確定。

## runtime DTと起動成功版DTの比較

比較可能なDTBは、今回起動中のruntime FDTと2026-11-15保全のKVM起動成功版no-CQE/100MHz DTB（148,753 bytes、SHA-256 `a6bef90e18c0a16934e6c4196fea60408a1fed08b6ef9b62c7fbe5d7c5632d91`）に限る。両方を`dtc`でDTS化した差分は308行。主な差はLK runtimeが追加したchosen bootargs/bootslot、pstore/ramoops指定、vendor raw-data/debug node、大量のreserved-memory/mblock値である。これらの動的・個体依存領域を静的DTSへコピーしてはならない。

テキスト差分では`netsys/ethernet/SGMII/MT7531`、`11230000.mmc`、USB/PCIe、I2C/SPI/PWM/GNSSの主要機能ノードに実質的な値変更は見つからなかった。したがって、このDT比較からLAN失敗を新たなDT差分へ帰属できない。全nodeのphandleを正規化したproperty-by-property比較、`aliases`比較、純正DTB、Wi-Fi PHY成功版、BLE/GNSS/PWM/LTE成功版との比較は未完了であり、該当版の実物DTBがない機能は差分を推測しない。

次期DTSでは、実測済みMT6990 NETSYS 2 MAC、PCS/SGMII参照、MT7531 DSA/CPU port記述、P44 rootのPARTNAME/PARTUUID一意解決、eMMC no-CQE/100MHz方針を維持する。LKが起動時に加えるmemory map、OEM rawdata、serial/device info、校正情報、boot profiling値は含めない。

## Kernel config・moduleの原因分析

| 機能 | 実config/files | 実行時binding | 判断 |
|---|---|---|---|
| CPU frequency | `CONFIG_CPU_FREQ=y`, `CONFIG_ARM_MEDIATEK_CPUFREQ=y`; OPP tableあり | cpufreq policyなし | 参照したkernel source candidate `drivers/cpufreq/mediatek-cpufreq.c`のmachine match table（約835–853行）にMT6990がない。running Imageとのsource identityは未証明。generic driverを有効にするだけでは不可。MT6990 CPU-HVFS/voltage/clock契約の実装が必要 |
| I2C | `CONFIG_I2C=y`, `CONFIG_I2C_MT65XX=y` | DTに`mediatek,mt6990-i2c` nodes、adapterなし、driver未結合 | 参照source candidate `drivers/i2c/busses/i2c-mt65xx.c`のcompatible table（約524–539行）にMT6990なし。DT/候補sourceのmatch不足を確認。running Imageとのsource identityは未証明。別SoCのcompat data流用は未検証 |
| SPI | `CONFIG_SPI=y`, `CONFIG_SPI_MT65XX=y` | DTに`mediatek,mt6990-spi` nodes、SPI deviceなし | 参照source candidate `drivers/spi/spi-mt65xx.c`のmatch table（約232–274行）はMT6991を含むがMT6990はない。running Imageとのsource identityは未証明。MT6991 dataの流用をしない |
| PWM/fan | `CONFIG_PWM=y`, `CONFIG_PWM_MEDIATEK=y`; runtime DTは`compatible="mediatek,mt69xx-pwm"`; PWM node未bind、pwmchipなし、`pwm-fan: Could not get PWM` | 保持candidate source (`drivers/pwm/pwm-mediatek.c`)とPR #7候補は7ch、base `0x80`、stride `0x40`、match `mediatek,mt6990-pwm`を持つがruntime DT compatibleと一致しない。実稼働Imageの厳密なsource provenanceは未確定。providerが出ないのがfan deferの直接理由 |
| RTC | `CONFIG_RTC_CLASS=y`, `CONFIG_RTC_DRV_MT7622=y`（選択configに記録） | rtc class/deviceなし | 参照source candidate `drivers/rtc/rtc-mt7622.c`のmatch table（296–301行）は`mediatek,mt7622-rtc`/`mediatek,soc-rtc`のみ。runtime DTのMT6685 PMIC RTC childとは一致しない。running Imageとのsource identityは未証明。対応MFD child driverが必要 |
| GNSS | `CONFIG_GNSS` unset、GNSS classなし | `gps@18C00000` deviceあり、driverなし | GNSS APIだけでは足りない。MT6990 conninfra/ATF/PMIC/clock/reset、reserved-memory、専用transport/firmware/userlandが必要 |
| Bluetooth HCI | `CONFIG_BT` unset | BT/HCI classなし、physical HCI transport未確定 | C号機ESP32-C3は`ttyS1`上のESP-ATでLinux HCI controllerとは別。`btattach`のみでは解決しない |
| Wi-Fi modules | cfg80211/mac80211/mt76 modules構成、P44に`mt76`, `mt76-connac-lib`, `mt7996e`あり。vermagicは対象release一致 | cfg80211のみload、PCI 7990/7991 unbound | dependencies/PCI aliasはある。`CONFIG_MODVERSIONS`なしのためvermagicのみではABI完全一致を証明しない。firmware欠落でinsmod前停止 |
| USB | xHCI-MTK/MTU3 module構成 | dmesgにUSB2/3 root hub登録、外部deviceなし | controller/root hubまでPASS。外部device列挙・VBUS・データI/O未試験 |
| KVM | `CONFIG_KVM=y`、`/dev/kvm`あり | guest未起動、QEMU実行物なし | hardware API available。過去guest成功は別bootの記録 |

ここで挙げるdriver sourceの行番号はローカルに保持されたcandidate treeのもの。製造commitと稼働中Imageの完全なprovenanceがないため、実機で稼働したsourceの行番号として扱わない。過去成功版の全Image/config/DTB/firmwareが揃わないため、全config bit比較と完全なABI証明はBLOCKED。moduleのhash/vermagic/依存/aliasはprivate manifestにある。

## LAN根本原因の追加分析

### 既存startup serviceの定義と実行証拠

privateの`/run/terminal6/start-management.sh`はchecksumと一度だけ実行guardの後、次の処理を定義している。

1. `test23_netsys_fixedlink.ko mac_id=1`でNETSYSを作成。
2. `test23_mdio_switch.ko mac_id=1 cpu_port=5`でMDIO/MT7531/DSA treeを作成。
3. `test24_path_probe.ko writes=N`をload。
4. `eth1`と`lan2`をupしcarrier/speed/duplexを確認。
5. `space=3`, `reg=0x20`を読み、期待値`0x31120009`以外なら`writes=Y`, `phy_init=1`, `writes=N`を実行し、再読出し値を要求。

private journalには3本のmodule checksum成功、module load、および管理serviceの終了status=1が記録されている。しかし、scriptが出す`DEBIAN13_T6_SGMII1_BEFORE`、`phy_init`の適用ログ、再読出し値はjournalに見当たらず、どの条件分岐まで実行されたかは確認できない。別のkernel `phy_init` initcall記録からcustom module parameterの実行を推定してはならない。したがって、この起動でMMIO writeが実行されたかはUNKNOWNであり、監査者は再実行していない。module source照合後、`space=3`は`maps[1]`を選び、そのDT pathは`/sgmiisys@11305000`、`reg=0x20`はそのregmapのoffset 0x20と特定できた。これはsource上のmappingであり、実機のwrite実行記録ではない。

### ネットワーク層の到達点

| 層 | 根拠 | 判定 |
|---|---|---|
| raspi3→ケーブル→LAN2 | carrierあり、ARP試行時`lan2` RX増 | port/driver receive counterまで届く可能性が高い。captureなし |
| switch CPU port 5→NETSYS/MAC1 | `eth1` RX 0、`br-lan` RX 0、ARP/ping不達 | CPU packet path未成立 |
| fixed link | eth1 2500BASE-X link stateのstartup記録 | link stateはdatapath成功の証明でない |
| PCS setting | custom probe `space=3/reg=0x20` value 0 | 期待値不一致を確認。意味/根本原因はUNKNOWN |
| MT7531 | MDIO addr31 CREV raw `0x75310001`、PHY 0..4 bind、DSA tree logs | MDIO・tree setupの一部PASS、CPU forwardingは未PASS |
| in-tree PCS source candidate | `drivers/net/pcs/pcs-mtk-lynxi.c`: `SGMSYS_SGMII_MODE=0x20`（約55行）; MT6990 path writes `0x31120009`（約199–221行）とreset/power sequence | candidate sourceの事実。ただしrunning Image provenanceと`space=3`が同じregmapかは未確認 |

`test23_netsys_fixedlink.ko`, `test23_mdio_switch.ko`, `test24_path_probe.ko`はprivate build binaryがある（それぞれ78,560/55,464/71,984 bytes）。今回、対応sourceと固定製造runを回収し、実機の`/run`配置物とのhash照合を完了した（下記追補）。

### 次期LAN実装

- Source targets: `drivers/net/pcs/pcs-mtk-lynxi.c`, `drivers/net/ethernet/mediatek/mtk_eth_soc.c`, MT7530/DSA driver、board DTS `netsys@15100000`, SGMII1 PCS/syscon、MDIO/MT7531、CPU port5、LAN2 port1。
- CONFIG: 解決済み`NET_MEDIATEK_SOC`, `PCS_MTK_LYNXI`, `NET_DSA`, `NET_DSA_MT7530`をmanifest/CIに記録し、built-in/module依存を検証する。
- Init order: clock/reset/power provider → NETSYS syscon/MAC → driver管理のPCS/SGMII reset/config → MDIO/MT7531 → DSA CPU/external ports → bridge/address → networkd/SSH。手動MMIO pokeをservice pre-hookに残さない。
- 入手したcustom sourceから`space/reg`→regmap/base mappingを解読し、DTS/driverに由来を紐づける。source未回収の間、probeの再実行・未知reg書込みをしない。
- Isolated LAN acceptance: raspi3 eth0 `192.168.1.50/24`, target `192.168.1.1/24`, explicit route/sourceを使い、同一試行窓の`lan2`,`eth1`,`br-lan` counters、ARP reply、双方向ICMP/TCP/strict SSHを記録。carrierのみで合格にしない。

## Wi-Fi firmware/ABIの不足情報

firmware sourceは`drivers/net/wireless/mediatek/mt76/mt7996/mt7996.h`の要求定義とMCU初期化経路。現serviceは `_mt6990` suffixまたはgeneric名の**完全な一組**を選び、通常firmware pathへ配置する。

| 入力basename | request/役割 | 配置 | 過去成功版SHA |
|---|---|---|---|
| `mt7996_wa_mt6990.bin` または `mt7996_wa.bin` | `mt7996_wa.bin` (WA) | `/lib/firmware/mediatek/mt7996/mt7996_wa.bin`、必要時`_233` alias | NOT_FOUND |
| `mt7996_wm_mt6990.bin` または `mt7996_wm.bin` | `mt7996_wm.bin` (WM) | 同directory `mt7996_wm.bin`、`_233` alias | NOT_FOUND |
| `mt7996_dsp_mt6990.bin` または `mt7996_dsp.bin` | `mt7996_dsp.bin` (DSP) | 同directory `mt7996_dsp.bin` | NOT_FOUND |
| `mt7996_rom_patch_mt6990.bin` または `mt7996_rom_patch.bin` | `mt7996_rom_patch.bin` | 同directory `mt7996_rom_patch.bin`、`_233` alias | NOT_FOUND |

private `mediatek-firmware-files.txt`は0 bytes、実機で確認した8つのgeneric/MT6990-specific basenameも全てmissing、firmware serviceは`FIRMWARE_SOURCE_NOT_FOUND_NO_P26_FORMAT_ASSUMPTION`で終了。stock B read-only snapshotでは同個体EEPROM名ファイル以外の4 firmwareを確認できず、P44 manifestも空。firmware blob SHA/provenanceは**NOT_FOUND**。このためdriver未bindは独立原因と断言しない。module aliasはPCI IDs 0x7990/0x7991と一致し、dependencyは`mt7996e → mt76-connac-lib → mt76`。実機`modinfo`のvermagicは`6.18.63-debian-t6-proto2 SMP mod_unload aarch64`、依存は`mt76, mt76-connac-lib`。今回の読み取りで確認したmodule SHA-256は`mt76.ko=26ffb6bd648a8fa91b424bbcf890710f8695d679d45b372e2e7ba05b68449c2f`、`mt76-connac-lib.ko=9f2df583cc73c738f7a186f1ef16faffcb6919bdf915f4ec9cf09a3df1fa05a6`、`mt7996e.ko=c87f66f6573d5a4c3d1e829009fc42baf3223f1b0b958c4fc8a549b135e0fecd`。`CONFIG_MODVERSIONS`なしのため、vermagic/hash/dependencyだけで完全なABI整合性を証明しない。

P44 manufacturing/CIには、kernel module `MODULE_FIRMWARE` requestとP44 manifestの照合を加える。権利確認済みpayloadを含めるか、owner-private firmware seedの必要名・hashを明示し、起動前検査で欠落を診断する。個体EEPROM/calibration、proprietary firmwareは公開しない。修正後の試験はfirmware load→PCI bind→EEPROM/OTP→`phy0`→regulatory channelsを分離し、RF送信は別ゲートとする。

## 全周辺機能の状態・修正台帳

DT nodeの存在は物理実装や動作の証拠ではない。過去の成功はOS/bootを明記し、今回bootと混ぜない。

| 対象 | 今回の実測/状態 | 不足原因と確度 | 次期ビルド/受入 |
|---|---|---|---|
| CPU/cores | 4 Cortex-A55 online、Debian実行 PASS | 周波数制御とは別 | cores + thermal monitor、負荷試験別 |
| CPU frequency/OPP | `CPU_FREQ=y`, `ARM_MEDIATEK_CPUFREQ=y`, OPPあり、policyなし | generic MTK driver matchにMT6990なし。sourceで確認済み。HVFS/voltage/clock契約も必要 | 正しいMT6990 DVFS providerとregulator/OPPを実装、host表検査後にtransition/thermal試験 |
| CPU idle/power | CPU_IDLE unset、一部clock/scpsys driver bind | idle state/供給条件未確認 | SoC/power firmware contractを確認してから追加、idle/exit試験 |
| RAM/GIC/IRQ | MemTotal約1.76GiB、4CPU IRQ稼働 | runtime LK reservationsは個体値を含む | private reservationをDTSへコピーしない。validated memory owner map/IRQ確認 |
| DMA/IOMMU | MMC/NETSYS/CCCI DMA clients、IOMMU config absent | isolationを証明できない | map DMA clients/SMMU; descriptor bounds host tests。直接DMA操作なし |
| eMMC/P44 | P44 ext4 RW; actual 94,999,965Hz, HS400, 8-bit, 1.8V, CQE off; error counters0 | snapshotは長時間安定性ではない | no-CQE/100MHz維持、temp監視下でbounded hash I/O/長時間試験 |
| MMC naming/root | current `11230000.mmc`=`mmc1/mmcblk1`; other host deferred for missing vqmmc; cmdline candidate p26 but mounted p44 | probe/defer orderによる番号差が有力。根の番号固定は不可 | PARTNAME + unique PARTUUID; `/aliases`とprobe order test; boot candidate/final root別ログ |
| Ethernet/DSA | LAN2 ingress counter only、CPU path不成立 | 正確なPCS/MMIO根因未確定、custom source欠落 | 上記LAN専用計画 |
| Ethernet port mapping | DSA lan1..lan5、今回lan2 link | 外装コネクタとの対応未完 | isolated per-port cable map + traffic test |
| PCIe | 7990/7991 endpoints; 2 hosts; `11290000` probe `-110` | host-port timeout independently observed | PHY/clock/reset/supply source and DT graph, endpoint bind separate |
| Wi-Fi 2.4/5/6, MLO, mesh | current PHY none | 4 firmware missing causes startup stop; later probe unknown | firmware gate first, then PHY capabilities; 6GHz/MLO/mesh separate legal/peer tests |
| Bluetooth HCI | `CONFIG_BT` unset、HCI absent | physical HCI bus/firmware unknown。Linux HCI APIがないことだけで無線機能不在とは断定できない | transport proof and config/module; `HCI Read Local Version` acceptance |
| ESP32/BLE | current AT not refreshed | historical C-unit ESP-AT GATT Read/Write/Notify/Indicate with owned peer; not Linux HCI | dedicated UART-safe API, owner peer test, do not replace firmware |
| GNSS/PPS | DT gps node, no bind/class/NMEA/PPS | CONFIG absent; conninfra/ATF/PMIC/transport/firmware | follow local GNSS port doc; source, legal firmware, clock/IRQ contract before probe; data/fix/nav/PPS separate |
| LTE/5G/WWAN | CCCI/CCMNI interfaces exist but down/counters0 | Debian RIL/CCCI FS/MIPC/firmware lifecycle missing/unproven | rights-cleared control plane; no guessed commands; registration/PDN/LTE IPv4 then NR/IPv6 |
| USB2/3 | xHCI + MTU3, USB2/3 root hubs registered | no external device; VBUS/role unverified | known non-storage serial/HID enumerate, transfer, hotplug; no VBUS override |
| I2C/sensors | MT6990 nodes, config on, no adapters | retained source no `mediatek,mt6990-i2c` match | proper register/timing/DMA/clock compatible; known-device read only after binding; no bus sweep |
| SPI | MT6990 nodes, config on, no children | retained driver has mt6991 but not mt6990 match | validate IP variant, mode, DMA, CS/pins; host model first |
| PWM/fan | no pwmchip; fan deferred; runtime DT `mediatek,mt69xx-pwm` | inspected candidate driver matches `mediatek,mt6990-pwm` with 7-channel data, but exact source/image identity is unproven. The observed DT/driver-candidate compatible mismatch is concrete; do not infer the deployed kernel's exact table | compare running build provenance; validate PR7 data, clocks/pins/register offsets; align reviewed DT compatible+driver; then channel test, fan RPM/temp under cooling-safe threshold |
| Thermal | 13 LVTS zones, ~low-60s C snapshot, no cooling device | trip/cooling map absent; prior nvmem calibration warning | calibration source + cooling map + fan provider; no heat/cooling impairment |
| LEDs | DT candidates/API partial | class existence isn't physical LED output | safe mapping and reversible indicator test |
| Buttons | gpio-keys DT node | no verified input events/physical map | input node + short press test; avoid reset-long-press |
| GPIO/pinctrl | gpiochip API and pinctrl controller | line names do not prove external function | document verified consumers; do not toggle unknown lines |
| RTC/time | no RTC class/device; system clock Apr 13; no successful timesync evidence | RTC driver match lacks MT6685; no early clock source | MT6685 child RTC, network time service dependencies/fallback; retention/TLS test |
| Watchdog | mtk-wdt visible, timeout31s/inactive | feed/reset behavior untested | controlled offline watchdog/recovery test on disposable build |
| RNG/TRNG | MTK HWRNG config selected, no current registered source evidence | DT/driver match mismatch possible | match/probe in safe build, `rng_current` and source test; getrandom is not TRNG |
| Crypto engine | EIP97 node, no hardware driver/API evidence | SoC compatible/driver support unknown | validate accelerator driver/IRQ/DMA, crypto selftest/API usage |
| KVM/QEMU | `/dev/kvm` PASS; QEMU missing/not run | package absent in current root | package manifest; guest OpenWrt boot and isolated host-guest traffic. Historical guest pass is separate |
| audio/display/GPU | DT contains SoC multimedia/audio nodes; no functional test in this bundle | bind/firmware/userland unknown | driver map from dmesg/config, then tests only with known outputs/fixtures |

### 既知成功履歴の境界

| 機能 | 過去のOS/条件 | 今回のDebian boot |
|---|---|---|
| BLE GATT | C号機ESP32-C3 ESP-AT UART companionでowned peerにGATT read/write/notify/indicate。Linux HCIではない | NOT_RETESTED |
| GNSS | 純正Bのみ3D fix、GPS/GLONASS/BeiDou/Galileo navigation delivery | Debian driver未bind、データなし |
| LTE IPv4 | OpenWrt Stage10別kernel/userlandでping/DNS/TLS HTTPS | CCCI interfacesのみ、sessionなし |
| Wi-Fi | 別Debian candidateでPHY、2.4/5GHz STA/DHCP/ICMP/HTTPS、別条件AP smoke | firmware不足でmodule前停止 |
| PWM/fan | PR #7候補がMT6990 7ch provider/fan bindを報告。物理ファン回転は未確認 | pwmchipなし、fan deferred |
| USB | 過去boot root hub | 今回もroot hubs、external I/Oなし |
| KVM/QEMU | 過去KVM版でOpenWrt ARM64 kernel/procd、isolated DHCP/gateway ping | `/dev/kvm`あり、QEMUなし/not run |
| Ethernet | 別Debian/OpenWrt buildの通信履歴 | 今回LAN2-to-CPU path FAIL |

## 次期ビルド反映台帳

`CU25`はC unit / 2026-11-25 auditを表す。先行資料の`C4-*`をC号機/4号機と誤読しないよう以下に改名・置換した。

| ID / 優先 | Evidence・原因確度 | 対象変更 | CI/host受入 | 実機受入・副作用 |
|---|---|---|---|---|
| CU25-BOOT-01 / P0 | p26 candidateとp44 final root、mmcblk番号変動を確認 | initramfs root resolver、P44 manifest | PARTLABEL+UUID unique fixture、block order variation、mmcblkN参照禁止 | cold boot後同じP44 UUIDをmount |
| CU25-EMMC-01 / P0 | 95MHz/HS400/8bit/1.8V/CQE off、snapshot error=0 | DTS policy/check script | `supports-cqe` absent、max-frequency<=100MHz | bounded + long I/O。snapshot 0を耐久PASSとしない |
| CU25-LAN-01 / P0 | LAN2 RX only、CPU counters zero、startup `phy_init` invoked; exact map unknown | module source/provenance回収、標準 PCS/NETSYS/DSA graphとDTS | source-to-reg map、dt graph、kernel config dependency | isolated ARP, bidirectional ping/TCP/SSH and per-layer counters。追加probe pokeなし |
| CU25-LAN-02 / P1 | speed earlier1000/current100 | link diagnostics and test rig records | no forced speed without PHY proof | both-end negotiation repeated |
| CU25-WIFI-01 / P1 | 4 firmware absence blocks before insmod | P44 bundle manifest + firmware-request CI | required four names + legal payload or owner seed manifest | firmware→bind→EEPROM/OTP→PHY gates; no RF TX |
| CU25-WIFI-02 / P1 | aliases/deps/vermagic match but no MODVERSIONS, not full ABI proof | module build receipt with source/config/Module.symvers | modprobe dependency and symbol version/source receipt | driver probe after firmware, rollback; no RF TX |
| CU25-PCIE-01 / P1 | 11290000 probe -110 | PCIe PHY/clock/reset/supply DT graph | dtbs/source compare | endpoint link and AER separately |
| CU25-I2C-01 / P1 | current source no MT6990 compatible | correct MT6990 register/timing/DMA/clock data and match | driver/build/binding test | only known peripheral read after binding; no bus scan |
| CU25-RTC-01 / P1 | no RTC class; MT6685 child not matched | MT6685 MFD RTC child driver and time units | config/DT binding/service order | RTC retention, NTP after network, TLS/date check |
| CU25-TIME-01 / P1 | device date inaccurate | early fallback + timesync service after network | offline boot dependency tests | time sync and event timestamp check |
| CU25-THERM-01 / P1 | thermal zones without trips/cooling; fan deferred | calibration, trip/cooling map, PWM provider | DTS and thermal graph checks | sensor calibration, fan RPM under safe cooling |
| CU25-CPUFREQ-01 / P2 | generic driver lacks MT6990 match | HVFS/clock/regulator integration | OPP voltage bounds/source validation | frequency transition/throttle test |
| CU25-SPI-01 / P2 | MT6990 node vs no driver match | validated MT6990 SPI IP support | host register model/build | known peripheral bounded I/O |
| CU25-PWM-01 / P2 | DT says `mt69xx-pwm`, candidate driver/PR7 says `mt6990-pwm`; no provider. Runtime Image-to-source identity not proven | reconcile exact running source; review 7ch driver data and DT compatible, channel4 fan mapping, clocks/pinctrl | channel math/unit tests, DT binding and provenance gate | provider/fan bind, safe duty and RPM/temperature; retain cooling |
| CU25-GNSS-01 / P2 | no driver/class/transport | conninfra/ATF/PMIC/firmware + GNSS API | mock transport/firmware request | data, satellite, fix, nav, PPS separate |
| CU25-WWAN-01 / P2 | CCCI/ccmni down | rights-cleared modem lifecycle + userland | mock lifecycle | SIM registration/PDN/LTE; NR/IPv6 separately |
| CU25-BT-01 / P2 | Linux BT absent, ESP-AT separate | identify physical HCI or retain documented UART API | config/protocol tests | HCI version or owner BLE peer test |
| CU25-USB-01 / P2 | root hub only | modules and VBUS/role supplier graph | module/DT supplier check | known USB serial/HID I/O/hotplug |
| CU25-GPIO-01 / P2 | GPIO API only | verified DT consumers | reject unknown output lines | short button/LED test |
| CU25-RNG-01 / P2 | no registered TRNG source | match driver and node | Kconfig/probe checks | hw source read/health test |
| CU25-CRYPTO-01 / P2 | EIP97 node, no bound API | matching crypto driver integration | kernel selftests | crypto API selects device driver |
| CU25-KVM-01 / P2 | current KVM device, QEMU absent | QEMU packages/dependencies and isolated recipe | package dependency/guest test | guest boot, isolated host-guest traffic only |
| CU25-DT-01 / P1 | runtime vs KVM FDT differences mostly LK dynamic; other success DTBs absent | sanitized source DT and boot-time dynamic overlay provenance | reject private rawdata/calibration/serial payload; normalized diff | runtime memory/storage/net nodes validated |
| CU25-PROV-01 / P1 | source/config/module/fw not tied by complete receipt; custom net source missing | source provenance + generated manifest | kernel config/source/Module.symvers/module/fw hashes mandatory | compare loaded module+release, not vermagic only |

## 先行文書の訂正

先行文書のLAN欄は初期parameter `writes=N`だけで「MMIO追加書込みなし」と読める表現だった。script全文とjournalのinitcall記録に合わせ、起動時serviceが不一致時にwrite-enabled `phy_init`経路を呼んだ点を明記し、未確定なregister mappingを示すよう修正した。監査者が失敗後に初期化を再実行していない点は維持する。

## 今回行わなかった操作

新しいUART bulk extraction、生FDT/DTSまたは秘密値の公開、raspi3への新規SSH、管理LAN service再実行、probe module再ロード、追加MMIO書込み、I2C/SPI scan、GPIO/PWM出力変更、Wi-Fi RF送信、GNSS/WWAN制御、USB storage write、filesystem repair、slot変更、reboot、P25/P44/GPT変更は行っていない。

## 再開順

1. private archiveからtest23/test24 source、build inputs、`space=3` mapを回収し、既存startup `phy_init`の副作用を解析。register mappingが不明なまま再実機実験しない。
2. 次期P25/P44のsource/config/DT/module/firmware provenanceを一つのmanifestに固定。eMMC no-CQE/100MHzとPARTNAME/PARTUUID root selectionを維持。
3. Wi-Fi private firmware seedとbuild-time request-name/SHA checkを用意し、まず非送信でPHY registerまで検証。
4. RTC/time、USB fixture、network routingのユーザーランド課題を独立して受入。
5. SoC専用I2C/SPI/PWM/cpufreq/GNSS/WWAN実装は正確なclock/reset/power/IP contractを得てから行う。

維持必須: eMMC実clock約95MHz、HS400、8-bit、1.8V、CQE off、P44 ext4 root、今回snapshotのzero errors、純正slot B復旧性。zero error counterはlong-duration storage PASSではない。

## 関連資料

- [先行UART実機監査](CUNIT-LIVE-AUDIT-20261125.ja.md)
- [ハードウェアAPI一覧](CUNIT-INVENTORY-API-20261114.ja.md)
- [純正/OpenWrt/Debian比較](CUNIT-OPENWRT-DELTA-20261114.ja.md)
- [Wi-Fi/WWAN/Bluetooth/GNSS](CUNIT-RADIOS-20261114.ja.md)
- [GNSS MT6990移植進捗](https://github.com/Karin-Laboratory/Debian13-Terminal6/blob/codex/cunit-debian-gnss-port-20261120/docs/hardware/CUNIT-GNSS-MT6990-PORT-20261120.ja.md)
- [C号機ESP32 BLE実測](https://github.com/Karin-Laboratory/Debian13-Terminal6/blob/codex/cunit-esp32-ble-20261114/docs/hardware/CUNIT-ESP32-BLE-20261114.ja.md)
- [OpenWrt Stage10 status](https://github.com/Karin-Laboratory/openwrt-terminal-6/blob/main/docs/STATUS.md)

## LANモジュール由来と追加観測の追補（2026-11-25）

### 3本の管理モジュールの由来

非公開の11/25採取束に含まれる`/run/terminal6`ファイル一覧・SHA一覧を、製造run #43157680253のinitramfs内`MODULE-SHA256SUMS`および3つの`.ko`実物と照合した。3本ともステージ済みファイルのSHA-256が製造manifest・展開した製造物と一致する。journalには各ファイルの`sha256sum -c`成功後の`insmod`/kernel initcallがあり、同じ起動の`lsmod`にも3モジュールが現れる。したがって**この起動でロードされたモジュールの由来は、保存された起動記録の範囲で3本ともMATCH**である。実行中カーネル内の再配置済みメモリを直接ハッシュしたわけではない。

| モジュール | 由来判定 | 製造物と`/run`ファイルのvermagic | build ID |
|---|---|---|---|
| `test23_netsys_fixedlink` | MATCH | `6.18.63-debian-t6-proto2 SMP mod_unload aarch64` | `ac703ea9898088e1506c95653cb8885fc7a490ea` |
| `test23_mdio_switch` | MATCH | `6.18.63-debian-t6-proto2 SMP mod_unload aarch64` | `6cccecb3b8122d8d89e29f3de1d1c8a5d19140c5` |
| `test24_path_probe` | MATCH | `6.18.63-debian-t6-proto2 SMP mod_unload aarch64` | `6cdfdacde01ac356daf07d8ba82dfbb36e9f1a89` |

製造runが固定したソースcommitと、回収した旧source snapshotは3ファイルともGit blob IDが一致した。`test24_path_probe.c`のread-only source reviewでは、`space=3`は`maps[1]`、すなわち`/sgmiisys@11305000`を選択し、`reg=0x20`は同regmapのoffset `0x20`を読む。`phy_init id=1`はこのmapと`/sgmiiphy@11E60000`を選び、複数のregmap更新を含む。ただし、保存journalにはserviceのmodule checksum/load後にserviceがstatus=1で終了したことはあるが、`DEBIAN13_T6_SGMII1_BEFORE`、parameterの適用ログ、再読出し値はない。別のkernel initcall名`phy_init`をcustom parameter呼出しと混同せず、**このbootで該当write branchが実行されたかはUNKNOWN**とする。実機で再実行していない。

この詳細の根拠となる個別モジュールSHA-256、source blob ID、build run/artifact、private captureのhashは非公開の監査記録へ保存した。公開PRにはraw journal、個体識別情報、privateイメージを含めていない。

### パケット経路の到達点と次の切り分け

既存snapshotは`lan2`のRXカウンタ増加を示す一方、同じsnapshotではCPU側`eth1`と`br-lan`のRX増加を示していない。しかし、対向ARP要求とカウンタ差分を同一の短時間窓で採取した記録ではなく、ARP frame単位の到達は証明されていない。現時点で肯定できる最終地点は**LAN2側RXカウンタまで**で、switch CPU port、NETSYS/MAC、bridgeへの到達地点は未確認である。PCS値ゼロ単独を根因としない。

今回の追加パケット観測は`NOT_TESTED`。現在の物理隔離状態と既存raspi3 SSHセッションの排他所有をこの実行環境から確認できず、既存セッションには触れなかった。UARTデバイスもこのホストでは検出されず、UARTを開いていない。LAN3はLAN2の結果を流用せず`NOT_TESTED`とする。

次期切り分けでは、読み取り専用で、対向ARP送信の時刻と`lan2`、`eth1`、`br-lan`各RX/TXカウンタの同一窓前後差を対応させる。LAN3は物理ポート・配線を個別に確認した別試験とする。コード変更が必要と判明した場合は、まず`drivers/net/pcs/pcs-mtk-lynxi.c`のSGMII SYS1/PCS mode・reset経路、`drivers/net/ethernet/mediatek/mtk_eth_soc.c`のMAC1/PCS結合、MT7530 DSAのCPU port/VLAN経路を、実機DT graphと対比して一層ずつ検証する。証拠が増える前に`test24`の未知レジスタ値を書き換えない。

配布用P44の`lan2`/`lan3`を`br-lan`へ割り当てる修正（commit `bbb7c4a630619c5e4e5e8e43111ef6b2506a1851`、CI #45544269984）はソース試験・rootfs buildの結果であり、この実機でのLAN復旧は未実証である。

