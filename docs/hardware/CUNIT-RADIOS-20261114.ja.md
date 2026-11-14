# Wi-Fi / WWAN / Bluetooth / GNSS

2026-11-14、C号機Debian 13実測。無線送信・scan・AP起動・ペアリング・モデム接続・測位開始は実行していない。存在の列挙と標準APIの応答を確認し、不足する依存関係を特定した。

## Wi-Fi — PARTIAL

PCI 0000:01:00.0=14c3:7990と0001:01:00.0=14c3:7991、subsystem=14c3:6639。前者はmt7996e、後者はmt7996e_hif。MT7990のベンダー名とpciutilsの「MT7996」ファミリ表示を区別する。2 endpointは同じ無線構成のmain/HIFであり、独立した2無線チップ搭載の証明ではない。

ドライバはmt7996e→mt76_connac_lib→mt76、cfg80211/mac80211が基盤。既存terminal6-wifi-phy.serviceがfirmware/EEPROMを一時RAMへ用意し、1個のphy0とmanaged型wlp1s0を登録する。今回この初期化処理の再実行・修正・firmware交換はしていない。firmwareファイルはP26等の所有個体由来であり配布しない。

`iw phy`、`iw dev`、`iw reg get`でnl80211 APIの応答を確認。managed、AP、AP/VLAN、monitor、mesh等を広告する。interface combinationはAP<=16、managed<=19、合計<=19、同時チャネル<=1。これらはドライバ広告であって接続成功・性能保証ではない。

2.4/5/6GHzのband記述とHT/VHT/HE/EHTの情報があるが、6GHzチャネルは全てdisabled。global countryは00/DFS-UNSET。regulatory.db欠落の起動ログがあり、今回wireless-regdbをAPT導入したものの、規制ドメイン変更やPHY再起動による反映試験はしていない。6GHz/320MHz/MLOはBLOCKEDで、機能広告から実対応を推測しない。

ドライバログはEEPROMの初回取得失敗とdefault binへのフォールバックを表示。既存起動コードは同一個体由来のRAM上binを準備する設計だが、今回active EEPROMと元データの全量一致を再検証していない。そのため「汎用EEPROMに置換された」「正しい校正が確実に使用中」のいずれも断定しない。

firmwareのWM/WAはbuild time 2024-05-10、DSPは2023-11-13を表示し、MCU message 0012002d timeoutも発生。PCI側にCorrectable AER RxErrあり。通常接続可否を検証せず、PHY登録までのPARTIALとする。

過去C号機RC14/Linux 6.18.44では2.4/5GHz AP起動、クライアントDHCP・pingの記録があるが、今回のDebianでは実施していない。[OpenWrt比較](CUNIT-OPENWRT-DELTA-20261114.ja.md)参照。

次の試験はstorage修復後、同一個体校正のRAM内一致検査、regdb適用、timeout発生箇所のソース照合を先に行う。その後、所在地の規制と管理経路への影響を確認して2.4GHzの隔離AP/STA試験を行う。6GHzやMLOを先に有効化しない。

## WWAN — PARTIAL / データ通信BLOCKED

CONFIG_MTK_ECCCI_DRIVER=y、ECCCI_CCIF=y、DATA_PLANE_TYPE=3、MTK_NET_CCMNI=y。platformにdriver_modem、ccci_hif_ccif、ccci_hif_dpmaifが結合する。CCIFは0x10209000、DPMAIFは0x10011000のDT資源を参照。`ccmni0`〜`ccmni20`の21個とCCCI character device群を列挙した。

制御候補としてttyC0/ttyC2/ttyCMBIM、ttyCMIPC0〜14、ccci_monitor、ccci_fs、ccci_rpc等がある。名前だけで標準AT・MBIM・QMI互換と判断しない。標準USB cdc-wdm/wwan制御デバイスは探索範囲で見つからず、SIM・registration状態を返す既知の稼働ユーザー空間サービスも確認できなかった。

`ip -s link show ccmni0`はDOWN、IPv4未付与、RX/TX=0。この結果はSIMが存在しない、モデムが壊れている、あるいは契約がないという証拠ではない。ccmni netdev登録と無線attach/PDN確立を区別する。現在のインターネットはEthernet/NAT経路でありWWAN成功ではない。

libqmi-utils 1.36.0とlibmbim-utils 1.32.0はツールとして導入したが、CCCI端点へQMI/MBIM要求を送信していない。ttyCMBIMに推測した要求を送ることは、サービス競合やモデム状態変更につながる。ModemManagerの自動probeも起動していない。

MEDMCUはdriver結合、mailbox IRQとrpmsgデバイス1件があるが、そのconsumerは未結合。これはモデムが通信readyという証明ではない。専用firmwareの版・初期化順・CCCI FS/relay・SIM/RILの依存関係は、公開可能なソースと既存資料で先に照合する必要がある。

過去Stage10のLTE IPv4は[公開された証拠要約](https://github.com/Karin-Laboratory/openwrt-terminal-6/blob/main/docs/evidence/lte-stage10.json)にping/DNS/TLS HTTPS成功がある。別カーネル・専用ユーザー空間による履歴であり、DebianでLTE/NR/IPv6が使えるという結論にはしない。[transportの境界](https://github.com/Karin-Laboratory/openwrt-terminal-6/blob/main/docs/MODEM-TRANSPORT-HOST-SAFETY.md)も参照。

## Bluetooth — BLOCKED

**追加調査による補足:** [ESP32-C3のUART AT照会](CUNIT-ESP32-C3-20261114.ja.md)は成功した。以下のBLOCKEDはLinuxの標準HCI経路についての判定であり、BLE機能を持つ外付けcompanionが存在しないという意味ではない。

`# CONFIG_BT is not set`。`modinfo bluetooth`と`modinfo btmtkuart`はModule not found、`btmgmt info`はUnable to open mgmt_socket。AF_BLUETOOTH/SOCK_RAW/BTPROTO_HCIはerrno 97（Address family not supported by protocol）。BlueZを導入するだけではカーネルHCI APIは生えない。

HCIコントローラ、USB/SDIO Bluetooth endpoint、専用Bluetooth UART transportは未検出。`ccci_bt`というノードとconsys/clock関連DTの文字列だけではBluetooth実部品の存在・バス・Classic/LE対応を断定できない。rfkillデバイスもなく、rfkill listは終了1。

BlueZの[管理API](https://bluez.readthedocs.io/en/latest/mgmt-api/)はカーネルのHCI control socketを前提とする。今回はその入口が欠けているため、コントローラ起動やHCI Read Local Version試験へ進めない。ペアリング・送信なし。単一vendor koだけをロードして解決できる状態ではなく、まずtransportの資料と対応カーネル構成が必要。

## GNSS — BLOCKED / 信号対応UNKNOWN

DT `/gps@18C00000`は`mediatek,mt6990-gps`、複数reg領域（conn infrastructure 0x18000000、GPS 0x18c00000、dynamic 0x18d00000等）、11個のinterrupt指定、reserved-memoryへの参照を持つ。platform名は最初のregに由来する18000000.gpsで、driver未結合。`/consys@18000000`も専用transportの候補で未結合。

CONFIG_GNSS未設定で標準GNSS class/devノードはない。vendor driverなら標準GNSS class以外のAPIも可能だが、今回stp/gpsの既知char-deviceと稼働GNSS daemonは確認できず、gpsdに渡せる実証済みNMEAストリームもない。gpsdによるポート自動probeや位置の採取は実施しない。

GNSSはSoCのconsys・予約メモリ・専用firmware/PMIC連携を要する候補であり、モデムATコマンドだけで動くと仮定しない。測位開始・終了・衛星メッセージ・GNSS時刻同期はDebianで未検証。現在のNTP同期をGNSS時刻同期と混同しない。

過去[B号機純正OSの報告](https://github.com/Karin-Laboratory/openwrt-terminal-6/blob/main/docs/GNSS-RESEARCH-20261112.ja.md)では3D fix、GPS/GLONASS/BeiDou/Galileo navigation message配送が実測されている。DebianやOpenWrtでのGNSS成功実績とは区別する。SBAS/L1SbとQZSS L1Sは過去報告でも未確認で、今回もUNKNOWN。firmware非対応と断定せず、transport、出力設定、受信環境、実捕捉/復調の証拠を別々に揃える必要がある。

公開物に座標、SVID時系列、生NMEA、SIM/端末識別子、factory calibration、純正firmwareは含めない。
