# CPU・起動・ストレージ・Ethernet・周辺機能の詳細

実測日2026-11-14。全体状態は[インベントリ](CUNIT-INVENTORY-API-20261114.ja.md)。DT参照は[棚卸しJSON](evidence/CUNIT-DT-INVENTORY-20261114.json)、コマンド応答は[抜粋](evidence/CUNIT-API-EXCERPTS-20261114.txt)。アドレスはsysfs/DT/資源表示から取得し、直接MMIOアクセスは行っていない。

## A. SoC・CPU・メモリ・割り込み

DT modelは`MediaTek evb6990_cpe_mt7990_emmc`。`lscpu`はARM Cortex-A55 r2p0、1 cluster、4コア、online 0–3を返す。DTの各CPUは`arm,cortex-a55`でclock-frequency=1,701,000,000 Hz。cpufreqはKconfig有効だがpolicyディレクトリがなく、現在周波数を取得・変更できない。CPU_IDLEは無効。性能比較用ベンチマークは、ストレージ障害後の負荷抑制のため保留した。

DT `/memory`は0x80000000から0x80000000 bytes（2 GiB）を記述。MemTotalは1,757,596 KiB。差分は予約メモリ・カーネル等を含み、DRAM故障や追加メモリの証拠ではない。reserved-memory直下は32ノード。重なり・ブートローダー予約を考慮せず単純合算しない。

GICD=0x0c000000–0x0c03ffff、GICR=0x0c040000–0x0c23ffff。`/proc/interrupts`にGICv3と各CPUのarch_timer、UART、MMC、NETSYS、PCI MSI、MEDMCU/CCIF割り込みが存在する。CPUタイマーと通信IRQは実行中に使用されているが、各IRQの独立した注入試験はしていない。

clock系はclk-mt6990、clk-mt6990-ifrao/peri/vlpcfg等が結合。power-controller 0x12001000にmtk-scpsys、Ethernetのreset-controllerにti-syscon-resetが結合。これらの登録は全power domainの安全な切替を意味しない。今回クロック設定、reset、regulator設定を変更していない。IOMMU_SUPPORTは無効で、DMA機能をIOMMU保護済みと扱わない。

## B. ストレージと起動

eMMCはMMC product name `4FTE4R`、manfid=0x15、revision=0x8、製造年月02/2024、容量3.64 GiB。CID・serial・RPMB内容は取得・公開しない。life_timeは`0x01 0x01`、pre_eol_infoは`0x01`。これらは健康状態の粗い情報であり、今回のI/O障害を否定しない。

コントローラは`/mmc@11230000`、`mediatek,mt6990-mmc`、driver=mtk-msdc。regは0x11230000と0x11f00000、DT IRQ指定はSPI 0x104。実行時のMMC番号はprobe順で変わる。debugfs iosはclock要求200 MHz、actual 189,999,931 Hz、8bit、HS400、1.8 Vを返した。supports-cqeがDTにあり、起動ログもCQE有効化を記録。

| 区画 | PARTNAME | 列挙した大きさ・形式 | 今回の用途・検証境界 |
|---|---|---|---|
| P1 | misc | 512 KiB | 既存read-only bootctl statusのみ |
| P25 | boot_a | 32 MiB | カーネル起動の既存経路。内容再読出し・flashなし |
| P26 | rootfs_a | 128 MiB、squashfs | 既存Wi-Fi起動処理の入力。今回書き込みなし |
| P38/P39 | boot_b/rootfs_b | 32/128 MiB | 純正slot B。内容検証・切替試験なし |
| P43 | user_data | 453 MiB、ext4 | 未マウント・未変更 |
| P44 | rootfs_data | 約2.5 GiBの区画、ext4 root | Debian稼働、追加APTと限定的修復のみ |

起動引数に`bootslot=a`がある。古い`root=/dev/mmcblk0p26`も残るが、実際のPID1はsystemdでrootはP44 ext4。起動引数だけで現在のrootを判定しない。既存initramfs/P44 handoffの独立した再製造・LK/ATF内部トレースは今回の対象外。

`terminal6-bootctl status`はA priority=15/retry=0/success=1、B priority=14/retry=0/success=1を返した。今回このツールの変更コマンドは呼ばず、boot-successサービスを変更・再実行していない。観測された再起動時には既存サービスが通常通り起動し、MARK_SUCCESSFUL_PASS/B_unchangedを記録。P1の全量一致やLK試行回数の一般仕様をこのstatusだけで主張しない。

**rootfsの書き込み安定性は未達。** [障害記録](CUNIT-STORAGE-INCIDENT-20261114.ja.md)を参照。読み取りベンチ、書き込みベンチ、fsck修復、eMMCモード変更は実施しない。

## C. Ethernet

NETSYSは0x15100000。現状はインツリーの完成したDT bindだけで成立している構成ではなく、既存`test23_netsys_fixedlink`、`test23_mdio_switch`、`test24_path_probe`モジュールとmtk_soc_ethを使用する。`/proc/modules`にはこれらとmt76系が載る。driver/module名とvermagicは実機カーネルに対応しているが、公開リポジトリだけで同等構成を再製造できる証拠ではない。

MT7531はMDIO address=0x1f、既存ドライバログでCREV 0x75310001を読む。MDIO配下にMT7531 PHY 0–4、DSAにlan1–lan5が登録。CPU側のfixed linkはログで2500base-x / 2.5 Gbps Full。これはlan2の外部ケーブル速度1 Gbpsとは異なるリンクである。

`ethtool -i lan2`はdsa、`ethtool -i eth1`はmtk_soc_ethを返す。lan2はPHY1、link=1000 Mb/s Full、lan3はlinkなし。lan1–lan5の全てが外装コネクタとして配線されているとは断定しない。SGMII1初期化は既存の起動処理に依存し、今回reprobeやresetはしていない。

標準APIはrtnetlink、ethtool netlink/ioctl、sysfs netdev statistics。`ethtool -k`で広告されたchecksum/segmentation等の状態と、実際のPPE/flow/NATオフロードは別物。今回はbridge VLANやswitchdevの設定を変更せず、hw offload実効性を測定していない。

メモリ上だけで4,194,304 bytesをC号機から直結gatewayへ転送し、gateway計算SHA256の応答と送信payloadのハッシュ一致を確認。C側計時0.081320秒、412.621 Mbps（応答待ちを含む）。受信側計時は416.740 Mbps。単発・一方向・小標本であり、線速や長時間安定性を保証しない。直後の管理通信も維持した。キャプチャは行わず、他機器トラフィックや認証情報を収集していない。

スナップショットのlan2 Tx/Rx CRC・dropは0、eth1 rx_fcs_errors/overflow/checksum_errorsも0。MACはドライバ生成値を使っているログがあり、工場MACの適用は未実証。個体MAC・校正データは公開しない。

## H. 周辺機能

- **thermal:** `mtk-soc-temp-lvts`、reg 0x1100b000/0x1100c000。soc_max、CPU little 0–3、GPU 0–1、infra、connsys、MD 0–3の計13 zone。57.696〜65.471°Cの数値を読み取ったが、起動時にnvmem cell e_data1取得失敗があり、校正精度は不明。外部温度計比較・冷却制御試験なし。
- **GPIO:** `/pinctrl@10004000`にmt69xx-pinctrlが結合。GPIO character ABI v2をgpiod 2.2.1で列挙し236 lines。GPIO53はconsumer=reset。GPIO出力・reset線を触らず、番号だけから外装機能を推定しない。
- **UART:** mt6577-uartが3デバイスに結合。管理consoleはttyS0、MMIO 0x11002000。gateway USBシリアルで115200 loginプロンプトを確認しtermiosを復元。UARTの認証ログイン・他UART pin割当は未試験。
- **I2C/SPI/PWM:** ドライバ登録はあるが対応コントローラに結合せず、bus adapter/child deviceが出ない。モジュールが見つからないというmodprobe dry-run出力だけでbuilt-inを「未実装」と判断しない。CONFIG_I2C_MT65XX/SPI_MT65XX/PWM_MEDIATEK=yとdriver登録を併記する。
- **LED/ボタン/ファン:** mt76-phy0 LEDだけがclassに現れる。gpio_leds、pwmleds、AW9523B、gpio-keys、pwm-fanはDT候補。fanはPWM取得失敗でdeferred。光学表示・押下・回転・回転数は未確認。
- **USB:** mtk-xsphyのPHY結合はあるがmtu3/xhciホストは未結合、USBデバイス列挙なし。CONFIG_USB_XHCI_MTK/USB_MTU3=mだが対応koを確認できず、モジュール不足とsupplierリンク警告が残る。role/VBUS/power変更は行わない。
- **RTC:** classにrtcなし。MT6685配下RTCのDT記述だけで搭載確認しない。時刻はtimesyncdによるNTP同期を使用。
- **RNG/暗号:** rng_available/currentはnone。`getrandom(32)`は32 bytesを返すがソフトウェア乱数APIの試験に限る。EIP97とTRNGは未結合。AF_ALG SHA256要求はerrno 97で、CRYPTO_USER_API_HASH等は無効。CPU aes/sha系命令広告をSoC暗号化エンジンの動作証拠にしない。

初期化や不足ドライバの追加は、ストレージ安定性と正しいcompatible/clock/reset/power依存の確認後に進める。今回新しいモジュールのロード・アンロードは行っていない。
