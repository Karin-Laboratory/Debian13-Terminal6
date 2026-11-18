# C号機 純正Linux基礎調査とP25/P44設計判断

調査日: 2026-11-18 JST  
対象: 所有者指定のC号機、純正slot Bを中心とする読み取り専用調査  
状態: 設計判断と証拠境界を記録。機能移植、設定変更、デバイス再初期化、書込み、再起動は実施していない。

## 要約

今回の最重要所見は、純正Bで通信できることと、安定P25候補の管理LAN設計が同じ初期化経路であることはまだ示されていない点である。純正Bは現在の観測で`eth0`と`eth0.1`/`eth0.2`を用い、管理IPを持つ`br-lan`へこれらを接続していた。`eth1`はDOWN、`lan2`というDSA netdevは見えなかった。対して安定P25候補は、built-in NETSYS/PCS/SGMII/MT7531 DSAを前提に`eth1`と`lan2`を起動時に要求する。したがって、この候補のP25起動、該当DTの有効化、MAC選択、PHY/PCS/MDIO/DSA probe、パケットRX/TXは一連の未達ゲートである。

純正BのARP応答3/3と、先行するDebian AのARP無応答は所有者の2026-11-18記録であり、今回の読み取り調査は純正Bの基準状態を補ったもの。Debian側の失敗ログを今回取得していないため、原因は特定していない。

## 取得方法と個体・版の整合性

- raspi4へSSH接続し、既知のhost-keyを厳格に検証する設定で、所有者が指定した管理経路からroot SSHを実施。
- 実測: `uname -a`はLinux 5.4.238 / aarch64、`/proc/cmdline`は`bootslot=b`と`root=/dev/mmcblk0p39`、OpenWrt releaseは21.02.7、`br-lan`は`192.168.3.1/24`。
- 今回の`/etc/knos-config/INPUT_VERSION`は`1.00.10`を返した。作業依頼に添付された過去の記録にある1.01.80とは一致しない。hostnameコマンドはEmergency/BusyBox環境になく、`uname -n`は`SBA6D`を返す。所有者指定のIP・slotと整合するが、公開可能な固有IDで個体を独立照合していないため、ファームウェア版の差を保留事項にする。
- 今回の状態は瞬時の読み取りスナップショットであり、純正起動順・コールドブート再現性を新たに試験していない。
- 生のネットワーク出力に含まれるMAC、個体ID、秘密情報はこの公開資料へ転記しない。

## P0 管理LAN: 純正経路とP25候補

### 今回の純正B実測

| 項目 | 今回の読み取り結果 | 判定上の境界 |
|---|---|---|
| `eth0` | UP、carrier=1、driver symlinkは`mtk_soc_eth`、DT nodeは`netsys@15100000/ethernet@15100000` | MAC/NETSYS netdev登録とリンク状態。CPUの管理パケット通過はこれだけでは証明しない |
| `eth1` | DOWN。driver pathは`mtk_soc_eth`配下を指すがcarrier値なし | 外部管理portやSGMII1として動作中とは言えない |
| `br-lan` | UP、`192.168.3.1/24` | L3アドレス設定のみでハードウェアのRX/TX証明ではない |
| bridge ports | `eth0.1`, `eth0.2`, 無線netdev群等 | `eth0`上のVLAN netdevとbridge構成を確認。スイッチの全port/VLAN実装を確定しない |
| MDIO/DSA | 今回のBusyBox sysfs列挙ではMDIOデバイス情報を得られず、`lan1`〜`lan5`は現れない | 純正DTBのノードの有無や物理ポート不存在を意味しない |
| PCI/USB | sysfsに各busデバイスは列挙されるが、今回の簡易取得では識別子を保存していない | endpoint・controller数や機能状態はNOT_TESTED |
| Kconfig/log | `/proc/config.gz`の絞込で`MMC_MTK`, `MMC_CQHCI`, `NET_DSA`, `NET_DSA_MT7530`, `PHYLINK`, `USB_MTU3`, `USB_XHCI_HCD`の`=y`行を観測。絞り込みdmesgからEthernet初期化行を得られず | grepに出ないconfigの値やEthernet logを推定しない |
| modules/interfaces | `mt_wifi`, `btmtk_uart`, `bluetooth`, `conninfra`, `gps_drv`が`lsmod`に見え、vendor Wi-Fi netdev群が列挙 | moduleロード/if UPは機能通信、HCI登録、GNSS測位を証明しない |

所有者の先行記録では純正Bの同じ有線管理経路からARPが3/3成功。これは純正BのL2到達を確認するが、今回の`eth0`/bridge構成のどの物理portが応答したか、またDebian P25候補の同じ経路が動くことを証明しない。

### P25候補との対応

公開P25の解決済みKconfig契約は、少なくとも以下を`=y`に要求する（PR #25のcommit `9128d92d445b3753ca605aea85ffcd9f6190a50e`で確認）。

```text
CONFIG_ARCH_MEDIATEK=y
CONFIG_NET_VENDOR_MEDIATEK=y
CONFIG_NET_MEDIATEK_SOC=y
CONFIG_NET_DSA=y
CONFIG_NET_DSA_MT7530=y
CONFIG_NET_DSA_MT7530_MDIO=y
CONFIG_PCS_MTK_LYNXI=y
CONFIG_PHYLINK=y
CONFIG_BRIDGE=y
CONFIG_COMMON_CLK_MT6990=y
CONFIG_COMMON_CLK_MT6990_PERI=y
CONFIG_PHY_MTK_MT6990_SGMII=y
CONFIG_MFD_SYSCON=y
CONFIG_PINCTRL_MTK=y
CONFIG_REGULATOR=y
CONFIG_GPIOLIB=y
CONFIG_DEVTMPFS=y
CONFIG_DEVTMPFS_MOUNT=y
CONFIG_SERIAL_8250_CONSOLE=y
CONFIG_SERIAL_8250_MT6577=y
CONFIG_MMC_MTK=y
CONFIG_EXT4_FS=y
```

`NETSYS/MAC → PCS-Lynx/SGMII lane → MDIO/MT7531 → DSA CPU link/port → DSA user port → bridge/IP → networkd/SSH`は候補の依存図であり、全段を今回の純正調査でruntime traceしたものではない。既存C Debian記録では、MT7531 MDIO address `0x1f`、PHY 0–4、DSA `lan1`–`lan5`、CPU port 5の2500base-X fixed link、`lan2` PHY1の1Gbps Fullを確認している。しかしその時の経路は専用test23/test24 modulesを含む過去のDebian実験であり、PR #25の公開ドライバ・DTへそのまま外挿できない。

PR #25の公開起動gateは`eth1`と`lan2`の登録後に両方をUPにし、管理LAN readinessを確認する。P44の`systemd-networkd`が後段IP/DHCPと通常SSHを担い、initramfs rescue SSHはowner鍵と固定host keyが私有工程で与えられる場合だけ有効化する。現在の純正Bとの差から、P25では次の実測が必要:

1. 起動時DTでNETSYS MAC instance、SGMII lane、PCS、PHY、MT7531 CPU portの参照が一貫している。
2. built-in probeが時間順に成功し、`eth1`と想定DSA `lan2`が現れる（もしくは設計とスクリプトを実測に合わせて再選定する）。
3. carrier・速度・duplexを読むだけでなく、raspi4との双方向ARP/IP payloadを実測し、netdev counter/driver logと対応付ける。
4. 失敗時に`eth0`の純正VLAN経路、`eth1`、DSA名、CPU port、SGMII initial stateのどの境界で停止したかをUARTログで判定する。

公開DTS PR #23候補はcompile-only/未bootであり、今回の安定P25はPCIe/USBを無条件に有効化する候補ではない。Ethernet用DTSもcompile成功を物理配線・RX/TXと同一視しない。

### LANのP25/P44責務

- **P25 built-in**: NETSYS MAC、SGMII/PCS、MT7531 MDIO/DSA、PHYLINK、clock/reset/pinctrl/regulator/syscon依存の正確なmatch、UART、eMMC/EXT4。管理救援をP44故障時にも出すなら、ネットワークドライバとそのfirmwareをinitramfsから利用可能にする。
- **initramfs**: probe順序の待機とlink readinessのfail-closed判定、UART維持、鍵が個体化され隔離状態が明示された場合のみ緊急Dropbear。IP policyは明示設定し、bridge/NAT/DHCPを自動作成しない。
- **P44**: systemd-networkd、通常sshd/Dropbear、authorized_keys、ホスト鍵の個体化、IP/route/DNSポリシー、ログと保守ツール。
- **未確定**: pure stockのboard DTB全文・driver起動ログと公開OSS DTの差、`eth0.1/.2`から外装portへの物理対応、工場MAC取得経路。P25はDebian起動時のMACアドレス取得方針を確定し、factory MACを使うと主張する場合はその取得証拠を必要とする。

## P1/P2/P3 基礎設計マトリクス

| 機能 | 純正の実測証拠 | P25必須基礎 | P44後付け範囲 | 未解明事項 | 判定 |
|---|---|---|---|---|---|
| CPU/GIC/timer/console | 純正AArch64 Linux 5.4.238起動、UART console、IRQ系は既存C Debian台帳に実測 | MT6990 arch, GICv3, arch timer, earlycon, 8250/MT6577 UART、printk timestamp built-in | 診断ツール・userspace | pure stock bootログ全体との対応 | READY |
| DRAM/reserved memory/DMA | 純正Linux稼働。C Debian DTに2GiB memory宣言・多数reserved-memory | 正確なboard reserved-memoryを固定し、DMA/IOMMU状態を正直に表記 | userspace memory tools | 物理DRAM型番、IOMMU protection、各vendor reserved領域の用途 | FOUNDATION_ONLY |
| clock/reset/pinctrl/regulator | 純正eth0がMAC driver配下でUP。C Debian記録ではMT6990 clock/scpsys/reset/pinctrl driver結合 | SoC clock providers、syscon/reset、pin controller、regulator/GPIOをbuilt-in。consumerの正しいDT link必須 | 後付けconsumer module | 全power domain/clock relationshipと純正の初期化owner | FOUNDATION_ONLY |
| eMMC/P25/P26/P39/P43/P44 | pure B bootslot=b、root=/dev/mmcblk0p39、P44 rootfs_dataの過去RO確認。C DebianはHS400 ~190MHz/CQE由来write errors、100MHz/no-CQEは別の試験実績 | MMC MTK built-in、PARTNAME/rootwaitによる識別、`supports-cqe`なし、`max-frequency=<100000000>`、ext4 built-in。PR #3のno-CQE/100MHz証拠を基準 | fs tools/backup agents | pure stock実時MMC mode/clock/CQE、将来の長期耐久 | READY（安全策採用）; 安定性は限定試験のみ |
| 管理Ethernet / MT7531 | 今回: eth0 UP/driver bound、eth1 DOWN、br-lan + eth0.1/.2、所有者報告ARP 3/3 stock B。別のDebian実験ではDSA/lan2と通信PASS | `NET_MEDIATEK_SOC`, `NET_DSA`, `NET_DSA_MT7530`, `_MDIO`, `PCS_MTK_LYNXI`, `PHYLINK`, bridge built-in; exact MAC/PCS/MDIO/switch DT; initramfs driver path | networkd, SSH, DHCP/static policy | stock VLAN vs P25 DSA instance mapping、P25 actual RX/TX/ARP | BLOCKED (runtime path mismatch) |
| PCIe host / MT7990 endpoints | Pure stock compact probe didn't persist IDs. Existing Debian ledger found two host ports and endpoints 14c3:7990/7991; another host probe -110 | PCI core/MSI/MediaTek Gen3/MTK PCIe PHY built-in if boot-required; only DT ports with verified safe rails/reset | mt76/mt7996e as module + firmware/EEPROM staging, cfg80211/mac80211 | pure stock endpoint map, each root-port power/reset, MT7990 main/HIF cross-ref | FOUNDATION_ONLY |
| Wi-Fi PHY/AP/STA/6GHz/MLO | Existing C Debian PHY registration and separate previous AP/client successes across older kernels; current C runtime no RF tests in this investigation. Regulatory/EEPROM/MCU caveats in #6/#9 | PCIe plumbing as boot base; cfg80211/mac80211/mt76 modules okay only if dependencies available and calibration source verified | firmware staging/service, hostapd/wpa_supplicant, regulatory db, orchestration | active calibration provenance, exact band/regulatory entitlement, stable MCU bringup, MLO counters/traffic | BLOCKED |
| USB2/USB3/MTU3/xHCI/PHY | Pure B sysfs shows USB bus entries but this capture lacks endpoint/controller IDs. Existing Debian 2026-11-14 record: PHY bound, MTU3/XHCI unbound and devices 0 | USB core and PHY framework. Keep role-specific host/device nodes disabled until power/role/VBUS/resources verified; if mandatory boot dependency, built-in only after proof | xHCI/MTU3/serial/storage class modules, userspace | bus role, VBUS control, endpoint inventory; PR #23 experimental DTB not booted | BLOCKED |
| UART0/1/2 + ESP32-C3 | Pure B management console path via UART0 is established; historical Debian UART1 `/dev/ttyS1`, 0x11003000 with read-only AT query success | 8250/MT6577, clocks, pinctrl/IRQ for console UART built-in | serial clients and restricted ESP-AT tool | pure B port use and stock ESP controller daemon startup for this individual current version | FOUNDATION_ONLY |
| Bluetooth HCI vs ESP-AT | 今回の純正Bで`bluetooth`と`btmtk_uart` moduleはloaded。Debian側のHCI未登録/transport unresolvedは既存記録。ESP32 C3 AT queryは別実測 | `CONFIG_BT`とtransportはHCI endpointとUART/firmware route実証後に固定。console UART基盤を維持 | BlueZと独立したESP-AT制御API | 純正B HCI controllerの存在/登録、`btmtk_uart` transport・firmware・conninfra、ESP32との境界 | BLOCKED |
| GNSS/conninfra | 今回の純正Bで`gps_drv`と`conninfra` moduleはloaded。別の純正B報告で3D fix/navigation data。今回はGNSS controlなし。C Debian driver unbound/`CONFIG_GNSS` absent | GNSS class/common API optional。SoC conninfra/SMC/reserved memoryは正確なsource/ownership proof後 | gpsd/client, policy, data parser | 今回のBでdriver bind・firmware readiness・SMC/clock/powerは未調査。QZSS L1S/SBAS unknown | BLOCKED |
| LTE/5G modem / CCCI / CCIF / DPMAIF / CCMNI | Pure B process/modules not deeply collected this run. C Debian ledger: CCCI, CCIF, DPMAIF and 21 ccmni netdevs; data path unverified. Historical Stage10 OpenWrt has IPv4 data success | CCCI/CCIF/DPMAIF + required memory/DMA/IRQ built-in if OS boot/WWAN boot depends; exact device memory/firmware contract | RIL/telephony daemon, SIM/PDN control, firewall/routes | current SIM/firmware/IPC/service graph; ccmni registration != modem attach | FOUNDATION_ONLY |
| I2C/SPMI/PMIC/SPI | Existing Debian: controller drivers registered but no bound adapters/children; pure stock bus count alone not component proof | Generic bus controllers built-in only if validated; exact pinctrl/clock/reset/supplier links; PMIC nodes individual, not blanket | per-device modules and service | which DT clients physically populated, regulator/RTC/GPIO expander identity | BLOCKED |
| GPIO/pinctrl/AW9523/LED/button | Existing Debian: 236 GPIO lines; AW9523 candidate, no exterior proof; stock current capture did not enumerate users | GPIO/pinctrl built-in. Buttons/LED provider nodes only with circuit/physical binding evidence | LEDs/buttons policy and safe daemon | polarity, exact line, expander presence, button long-press behavior | FOUNDATION_ONLY |
| PWM/fan | Existing Debian PWM driver registered without pwmchip; pwm-fan probe deferred | PWM controller and provider DT only after exact clocks/pins/capture compare | fan curve and monitoring | physical fan/tach, fail-safe state, polarity | UNKNOWN |
| Thermal/watchdog | Existing Debian 13 thermal zones have values but calibration warning; watchdog driver present/inactive | thermal/watchdog core and SoC driver if safe; calibration nvmem must remain untouched | health monitoring policy | sensor accuracy, board thermal sensor identity | FOUNDATION_ONLY |
| RTC | Existing Debian RTC class empty; PMIC RTC only a DT candidate | RTC class driver only after PMIC silicon/bus verified | time sync/RTC policy | fitted PMIC and clock domain | UNKNOWN |
| TRNG/EIP97/crypto | Existing Debian hardware RNG none; EIP97 unbound; CPU SHA/AES instruction not engine proof | crypto API generic base; SoC engine driver only with matching compatible and verified DMA/clock/reset | crypto consumers | hardware engine identity/known-answer validation | FOUNDATION_ONLY |
| GPU/audio/display/video | Existing Debian DT shared SoC candidates unbound; no physical output evidence | Keep nodes disabled or inert until board evidence and vendor license/source match; avoid boot critical footprint | Userspace/media stack, firmware, plugins | SKU and physical components, proprietary ABI/source | UNKNOWN |
| MEDMCU/rpmsg/diagnostics | Existing Debian mailboxes/rpmsg device listed but consumer unbound | mailbox/rpmsg core only if base dependencies require; keep consumers conditional | protocol daemon | firmware ready state and documented IPC contract | FOUNDATION_ONLY |

## P25/P44の推奨区分

### P25へ固定するもの

1. boot-critical driversとprovider: UART console、eMMC、ext4/PARTUUID-or-PARTNAME handoff、clock/reset/pinctrl/regulator/syscon、NETSYS/DSA/PCS/SGMII/MDIO（ただし正しいmatching board DTを検証してから）。
2. 100MHz/no-CQE storage policy。CQEをruntimeで切り替えず、DT propertyそのものを欠落させる。
3. 初期RAM filesystem、UART fallback、initramfs側での管理LAN readinessとfail-closed救援SSHの仕組み。鍵・固定host keyは個体化の非公開工程に分離する。
4. `CONFIG_MODULES=y`、安定したrelease string、Kconfig/Module.symvers/System.mapと同じbuild ID・ABIの保存。
5. Verified DTだけを選ぶこと。PR #23のPCIe/USB試験用treeやSoC共通の未確認周辺機器を安定P25へ一括有効化しない。

### P44で追加可能なもの

networkd/SSH、Wi-Fi/WWAN/GNSS/Bluetooth userspace、firmware staging（再配布/個体校正規則を守る）、hostapd/supplicant、BlueZ、gpsd、telephony daemons、sensor/fan/LED policy、後付けkernel modules。モジュールはP25と同じsource/config/toolchain/build productsから作り、vermagicだけでなくModule.symvers ABIを照合する。P44が欠けてもLinuxが管理できるよう、ストレージ/LAN/console必須driversをP44 moduleに追い出さない。

### 必須な再製造条件

- 正式board DTBの根拠とhash、P25製造source pin、resolved `.config`を一緒に固定する。
- Ethernet driver/DTの登録だけではGOにしない。UART boot→interface bind→carrier→双方向payload/ARP→SSH、の各段階でPASSを記録する。
- 管理ポートは隔離環境で確認し、家庭LANとのsubnet overlapを解消する前にbridge/NAT/DHCPを足さない。
- P44 rescue/normal SSHは別鍵・ホスト鍵・port/known_hostsとして事前に安全に個体化し、ユーザー鍵無し画像をowner-readyと呼ばない。

## 既存証拠の再利用と限界

- PR #7 と `docs/hardware/CUNIT-INVENTORY-API-20261114.ja.md`: Debian機能台帳・driver bind/APIの実測を再利用。2026-11-14時点で、今回の純正runtimeそのものではない。
- PR #24: Bluetooth UART/HCI未解決を再利用。
- PR #8: GNSS/conninfraと信号対応の未解決を再利用。
- PR #4 と公開Stage10 evidence: CCCIと歴史的OpenWrt LTE dataplaneの境界を再利用。
- PR #23: PCIe/USB DT候補はexperimental compile-onlyとして扱い、実機PASSとしない。
- PR #3: C-unitの100MHz/no-CQE試験記録を再利用。長期信頼性保証に読み替えない。
- PR #25: Kconfig contract、P25/private buildの工程を読み取り。製造担当のブランチ、署名、実機操作には本調査から手を加えない。

今回、C号機上の読取り以外に、module reload、scan、GPIO/I2C/SPI access、MMIO、power/clock、network config、service操作、storage access、file transferをしていない。必要なログを公開できる形で整理しただけで、raw DTB、純正modules/firmware、calibration、SIM、MAC、機器固有秘密を添付していない。

## 未解決事項と次の最小調査

1. Firmware 1.00.10と以前記録された1.01.80の版差を、所有者が指定するC号機の再確認可能な非公開記録で照合する。公開識別子・serialを収集しない。
2. current stock Bのread-only DTで`netsys@15100000`と`/mmc@11230000`以下の実際のstatus/compatible/clocks/interruptsを抽出し、秘密propertyを除外したcanonical metadataを保存する。今回BusyBoxコマンドではそこまで取得していない。
3. vendor boot logから`eth0`, `eth1`, VLAN/DSA/SGMII driver namesのprobe順と、read-only `/sys`のdevice linksを対応付ける。
4. 対応するP25 unsigned candidateのUART起動後、同じ物理cableで`eth0.1/.2`か`eth1/lan2`のどちらが外装管理portへ出るかをread-only captureし、実パケットをowner-approved network testで照合する。
5. WLAN, USB, GNSS, WWAN, BT, I2C/SPI/PMICの純正DT/source/module load graphは個別研究PRの証拠が増えるまでFOUNDATION_ONLY/BLOCKEDのままにする。

この調査だけでは「全物理機能を洗い切った」「安定P25で全機能が使える」とは宣言しない。
