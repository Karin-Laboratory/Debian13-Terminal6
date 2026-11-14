# ハードウェア総合インベントリ・API対応表

2026-11-14、Debian 13 / 6.18.63-debian-t6-proto2での結果。過去のOpenWrt/純正OS実績は[比較表](CUNIT-OPENWRT-DELTA-20261114.ja.md)へ分離した。各行の状態は観測範囲に限定する。

| 対象 | 判定 | 接続・DT / ドライバ | APIと最小実測 | 制約 |
|---|---|---|---|---|
| CPU 4コア | VERIFIED | `/cpus/cpu@*`, arm,cortex-a55 | lscpu: 4 CPU、AArch64、r2p0 | 周波数実測・長時間負荷なし |
| CPU周波数制御 | BLOCKED | CONFIG_CPU_FREQ=y | cpufreq policyディレクトリなし、DT宣言1.701 GHz | DT値は現在の動作周波数ではない |
| CPU idle | BLOCKED | CONFIG_CPU_IDLE未設定 | Kconfig確認 | idle state有効化にはカーネル再構成が必要 |
| DRAM | VERIFIED | `/memory`: 0x80000000から2 GiB宣言 | MemTotal=1,757,596 KiB、ユーザー空間稼働 | 物理チップ型番・DDR仕様・全域メモリ試験なし |
| GICv3 / timer | VERIFIED | GICD 0x0c000000、GICR 0x0c040000 | `/proc/interrupts`で4CPU、arch_timerと通信IRQ増加 | IRQ注入試験なし |
| clock / power / reset | DRIVER_LOADED | MT6990 clk、mtk-scpsys、ti-syscon-reset | platform driver結合とDT参照 | rate/電源/リセット変更は管理経路に影響するため保留 |
| DMA / IOMMU | PARTIAL | CCIF/DPMAIF、MMC、NETSYS使用。IOMMU_SUPPORT未設定 | 通信とroot読み取り。DMA関連DT/IRQ列挙 | DMAメモリ直接操作なし、IOMMU保護なし |
| thermal LVTS | PARTIAL | `/lvts@1100b000`, mtk-soc-temp-lvts | 13 zone、57.696〜65.471°Cの値 | nvmem e_data1取得警告、絶対温度精度未検証 |
| watchdog | DRIVER_LOADED | 0x12007000、mtk-wdt | sysfs identity、timeout=31、inactive、nowayout=0 | watchdogデバイスを開かず発火未試験 |
| eMMC / P44 ext4 | PARTIAL | `/mmc@11230000`, mtk-msdc、MMC 4FTE4R | root RWでDebian稼働、HS400 8bit | **CQE write timeout・実ファイル破損を観測** |
| P25/P26・A/B | DETECTED | GPT boot_a/rootfs_a、boot_b/rootfs_b | パーティション表とread-only bootctl status | 区画内容同一性・切替・retry遷移試験なし |
| Ethernet MAC / MT7531 | VERIFIED | NETSYS 0x15100000、MDIO 0x1f、mtk_soc_eth/mt7530-mdio/DSA | SSH、ethtool、4 MiB内容一致転送 | 性能は単発値、hw offloadの実効性未検証 |
| LAN2 | VERIFIED | MT7531 PHY 1、lan2@eth1 | 1000 Mb/s Full、RX/TX、CRC/drop 0のスナップショット | ケーブル抜差し試験なし |
| LAN3・他DSAポート | DETECTED | MT7531 PHY 0〜4、lan1〜lan5 | lan3: Link detected=no | 実コネクタと全論理ポートの一対一対応は未実証 |
| Wi-Fi | PARTIAL | PCI 14c3:7990/7991、mt7996e/mt7996e_hif、mt76 | nl80211 iw phy/dev、1 PHY、managed/AP広告 | EEPROMフォールバック表示、MCU timeout、AP/STA未試験 |
| 6 GHz / MLO | BLOCKED | PHYに6GHz/EHT項目はある | 列挙のみ、6GHz全チャネルdisabled | 接続・MLO・320MHzを実証しない |
| WWAN | PARTIAL | CCCI driver_modem、CCIF、DPMAIF、21 ccmni | 制御ノード・ドライバ列挙、ccmni0 RX/TX=0 | SIM・registration・PDN・LTE/NR/IP通信は未検証 |
| MEDMCU / mailbox | DRIVER_LOADED | `/medmcu@15f00000`, medmcu、rpmsg | IRQとrpmsgデバイス1件列挙 | consumer未結合、IPC応答・firmware動作未実証 |
| GNSS | BLOCKED | `/gps@18C00000`, mediatek,mt6990-gps、未結合 | DT/予約メモリ確認、標準/dev/gnssなし | GNSSカーネル機能無効、専用初期化経路なし |
| Bluetooth | BLOCKED | 物理transport未確定 | btmgmtとAF_BLUETOOTHが失敗、errno 97 | CONFIG_BT未設定。`ccci_bt`はHCIの証拠ではない |
| ESP32-C3-MINI-1 | VERIFIED（AT照会） | UART1 0x11003000 / ttyS1、115200 8N1 | AT/GMR/CWMODE?/BLEINIT?全てOK | ESP-AT 3.1.0.0-dev。Linux HCIとは別、無線実通信未試験 |
| GPIO / pinctrl | VERIFIED | mt69xx-pinctrl、pinctrl_paris | gpiodetect/gpioinfo: 236 lines、GPIO53 consumer=reset | ライン要求・出力変更・電気的測定なし |
| I2C | BLOCKED | 6コントローラDT、i2c-mt65xx登録済み | adapter=0、i2cdetect -l空 | compatible/clock/pinctrlの対応調査が必要 |
| SPI | BLOCKED | 4コントローラDT、mtk-spi登録済み | SPIデバイス=0、未結合 | proslic_spi等はDTのみ、物理実装不明 |
| PWM / fan | BLOCKED | `/pwm@12016000`, pwm-mediatek登録済み | pwmchipなし、pwm-fanはCould not get PWMでdefer | ファン物理搭載・回転未検証 |
| LED | BLOCKED | gpio_leds/pwmleds/AW9523BのDT記述 | LED classにmt76-phy0のみ | 外装LEDの配線・制御未検証 |
| ボタン | UNKNOWN | gpio-keys DTあり、未結合 | 入力デバイス登録なし | 押下試験なし |
| UART | VERIFIED | 0x11002000、ttyS0、mt6577-uart | 115200でloginプロンプト、getty active | その他UARTの配線未確認 |
| USB | BLOCKED | `/usb@11201000`、mtu3/xhci-mtk=m、USB PHY結合 | USB列挙0、対応ko配備を確認できず | 外付け機器・VBUS・role切替試験なし |
| PCIe | PARTIAL | 0x11280000/11288000の2系統 | PCI 4デバイス列挙、Wi-Fi結合 | 0x11290000はprobe -110、AER Correctable RxErr |
| RTC | NOT_DETECTED | PMIC配下RTCのDT記述 | rtc class空、NTPで時計同期 | PMIC実装・RTC制御未確認 |
| TRNG | BLOCKED | `/trng@1020f000`, mediatek,trng、未結合 | rng_available/current=none | getrandom(32)成功はハードウェアRNGの証明ではない |
| SoC暗号化エンジン | BLOCKED | 0x10320000、EIP97 compatible、未結合 | AF_ALG: errno 97、CRYPTO_USER_API無効 | CPU命令機能とSoCアクセラレータを区別 |
| GPU / multimedia | UNKNOWN | Mali等のDTノード | 該当platform未結合 | SoC共通記述の可能性、物理/機能保証なし |

DETECTED/DRIVER_LOADEDは転送・測位・無線動作のVERIFIEDへ読み替えない。証拠は[evidence](evidence/CUNIT-API-EXCERPTS-20261114.txt)と[DT JSON](evidence/CUNIT-DT-INVENTORY-20261114.json)。未知候補の反証可能な試験は[DT解析](CUNIT-DT-UNKNOWN-20261114.ja.md)に記載。
