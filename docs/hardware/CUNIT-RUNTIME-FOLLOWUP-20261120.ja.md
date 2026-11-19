# C号機 Debian 周辺機能 read-only runtime follow-up（2026-11-20）

## 対象と安全範囲

2026-11-20 JST、C号機 `terminal6-debian`、Debian 13.7 / Linux `6.18.63-debian-t6-proto2`をraspi4経由で確認した。既存USB/Wi-Fi試験は[個別記録](CUNIT-USB-WIFI-RUNTIME-20261120.ja.md)に記載する。本書はESP32-C3 UART、GNSS、WWANの状態を更新する。

P25、P44永続データ、boot control、slot、GPTは変更していない。再起動やモデム制御コマンド、GNSS測位開始、BLE/Wi-Fiの初期化・scan・advertising・RF送信は行っていない。

## ESP32-C3 UART / ESP-AT

既存のbounded read-only client `esp32-readonly-at.py` を使用し、UART1 (`/dev/ttyS1`) で`AT`、`AT+GMR`、`AT+CWMODE?`、`AT+BLEINIT?`だけを照会した。ツールはUART ownerとconsoleを確認し、`flock`/`TIOCEXCL`で排他、115200 8N1を一時設定し、元のtermiosを復元する。今回4コマンドすべてが終端`OK`付きで完了した。

- Firmware応答: ESP-AT `3.1.0.0-dev`、ESP32-C3 / MINI-1。
- `AT+CWMODE?`は`+CWMODE:2`。これは設定値の照会で、SoftAP電波や接続の証明ではない。
- `AT+BLEINIT?`は`+BLEINIT:0`。照会時にBLEは未初期化。
- BLE scan、advertising、接続、ESP32 reset、firmware変更は未実施。
- transportはASCII ESP-ATでありLinux標準Bluetooth HCIではない。BlueZ/HCI実用化は未達。

| 段階 | 判定 | 内容 |
|---|---|---|
| ttyS1からのAT送受信 | PASS | 4 read-only query全てがOKで終了 |
| ESP-AT firmware情報取得 | PASS | GMR応答を確認 |
| ESP32 Wi-Fi機能 | NOT_TESTED | 設定照会のみ、無線開始・通信なし |
| ESP32 BLE | NOT_TESTED | BLEINIT=0を確認、scan等未実施 |
| Linux Bluetooth HCI | NOT_TESTED | 今回HCI操作なし。既存Debian調査ではCONFIG_BT未設定 |

## GNSS

今回の読み取り確認では`/sys/class/gnss`と`/dev/gps*`、`/dev/gnss*`が存在しなかった。過去の同一kernel系実機記録では`CONFIG_GNSS`無効、MT6990 GPS platform node未結合、専用transport/daemonなしとされる。標準GNSS API、NMEA、fix、衛星情報、GNSS時刻は今回も確認できず、測位試験はしていない。

過去の純正Linuxでの測位成功は別OS・初期化経路での実績であり、Debianで利用可能とはしない。次に必要なのは、公開可能なGPS/consysドライバと純正のfirmware・transport・reserved-memory初期化順を照合し、現在のP25で扱えるか、カーネル候補が必要か判断すること。位置情報取得・測位開始は別試験とする。

## LTE/5G WWAN

今回`ip -br link`で`ccmni0`〜`ccmni20`が列挙されたが、全て`DOWN`。`/sys/class/wwan`および`/dev/wwan*`は確認できなかった。これはCCMNI netdevの存在までで、モデム登録、SIM状態、LTE attach、PDN、IP通信の証拠ではない。AT/QMI/MBIM/CCCI制御要求は送っていない。

過去のOpenWrt LTE IPv4通信成功は、専用driver/userspace構成での別環境の実績。Debianのデータ通信へ一般化しない。次の作業は、CCCI/CCIF/DPMAIF/CCMNIに加えて必要となる専用firmware、CCCI FS/MIPC/RIL等の互換なユーザー空間と初期化順をソース・記録で特定すること。SIM識別子は扱わず、データ通信は適切な契約・許可・試験条件を確認してから別途行う。

## システム保全と再開地点

ESP-AT照会後もraspi4からC号機へのstrict-host-key SSHセッションは成功した。照会ツールはUART設定を復元した。GNSS/WWANに対する永続変更なし。USB、Wi-Fi、GNSS、WWANの今回の段階別判定と次の依存作業は、本書および[USB/Wi-Fi実機記録](CUNIT-USB-WIFI-RUNTIME-20261120.ja.md)を参照。

非公開の完全応答ログとツールはraspi4の非公開作業領域に保存し、公開文書にはMAC、位置、SIM/IMEI、calibration、認証情報、firmware実体を含めない。
