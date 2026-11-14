# C号機 ESP32-C3 BLE実測・制御API（2026-11-14）

既存の[UART・純正制御経路調査](CUNIT-ESP32-C3-20261114.ja.md)に追加する。main e728948 と未マージPR #3の追記を照合した。今回kernel、ESP firmware、GPIO、UART0、P25/P26/GPTは変更していない。個体アドレス・鍵・周辺広告payloadは収録しない。

## 結論と実機条件

ESP-AT経由でCentral/GATT Clientの実無線通信を確認した。Peripheralの接続も確認したが、ESP側の任意GATTデータベースは構築できず、ServerのRead/Write/Notifyは未実証。Linux HCIとしての利用は別方式である。

- ESP32-C3-MINI-1、UART1 `/dev/ttyS1`、115200 8N1、MMIO `0x11003000`、IRQ181。GPIO106はreset/enable候補のままで操作しない。
- AT `3.1.0.0-dev (799ebf3 ESP32C3 Mar16 2023)`、SDK `v5.0-541-g885e501d99`、compile Mar29 2023、Bin `2.5.0(MINI-1)`。
- 初期・最終状態は `BLEINIT:0 / CWMODE:2 / SYSSTORE:1`。UARTを使用する他プロセスがないことを確認して排他取得。
- 純正経路は `esp32_controller -> FIFO -> esp32_uart -> ttyS1`。前報の静的解析を引き継ぐ。純正バイナリは起動していない。登録BLEコマンドだけから純正の利用機能を断定しない。
- BLEのみを対象としClassic対応を推定しない。Wi-Fiモードは維持したが、SoftAPの実トラフィックとBLE同時負荷は未検証。
- 実機CMDQは0、今回終了時のkernel MMCエラー該当件数0。これは限定した観測でありeMMC全体の安定保証ではない。CQE修正・起動試験はPR #3の別サイクル。

## 実測マトリクス

|機能|結果|証拠・限界|
|---|---|---|
|初期化/終了|VERIFIED|role1/2と0 readbackを複数回。GPIO resetなしで再利用|
|Passive scan|VERIFIED|2秒、39 reports、11 unique、RSSI -80..-50 dBm。未知機器へ接続せず|
|広告|VERIFIED/PARTIAL|nonconnectable 3秒の設定/開始/停止OK（当該試行の受信未確認）。別のconnectable広告はraspi4から接続成功|
|Peripheral接続|VERIFIED|所有raspi4がCentralとして接続、MTU517イベント、切断|
|ESP任意GATT Server|BLOCKED|SRVCRE/STARTはOK。サービスUUID表示が0xのみ、CHAR? ERROR。任意UUID/Characteristicの無線Read/Write未実証|
|Central/GATT Client|VERIFIED|所有raspi4の独自128bit UUIDを探索し接続|
|Read/Write|VERIFIED|15 bytes Read、16 bytes Write/Readback一致。NUL・CRLF・OKを含むbinary|
|Notify/Indicate|VERIFIED|各3件、Indicateは対向Confirmも3件|
|MTU|VERIFIED|64設定・イベント・対向GATTのMTUが一致。別CLI試験では517|
|再接続|VERIFIED|完走試験で初回+2再接続、各探索/Readback成功|
|暗号化必須GATT|VERIFIED|SC_ONLY/NoInputNoOutput/16byte/no-bondを要求、AUTHCMPL待機、encrypt-read属性のRead成功|
|暗号方式の独立監査|PARTIAL|HCI/SMP packet capture未実施。要求パラメータから暗号強度を断定しない|
|Legacy/Passkey/Numeric Comparison|BLOCKED|今回未試験。人手認証経路を自動承認しない|
|Bond永続化/削除|PARTIAL|前後bond列挙0件。鍵の取得・bond作成・一括削除なし|
|UART異常復旧|VERIFIED/PARTIAL|ホストの擬似TTYでtimeout/不正frame/restart検知。実機の破壊的UART障害注入はしない|
|全機再起動後|BLOCKED|今回C号機全体は再起動せず。不要な管理停止を避けた|

証拠は[evidence](evidence/)の秘匿済みJSONL。command一覧は[対応表CSV](evidence/ESP32-BLE-COMMANDS-20261114.csv)。AT+CMD?は168件（BLE52件）で、登録と実行成功を区別した。全登録の形式flagsは対応表CSV、正確な投入構文・OK/ERROR・返答は[実行対応表](evidence/ESP32-BLE-EXECUTED-20261114.csv)。未実行のset構文を推測して対応済みとはしない。

## コマンド・プロトコルの注意

参照は公式[ESP-AT release-v3.0.0.0 BLE資料](https://docs.espressif.com/projects/esp-at/en/release-v3.0.0.0/esp32c3/AT_Command_Set/BLE_AT_Commands.html)。実機3.1.0.0-devと完全同版ではないため、実測応答を優先した。

- 空の `BLECONN?` は `+BLECONN:`。SECPARAM queryには余分なLFがある。
- Discovery中にもMTU/connection parameterイベントが混在する。単純なOK待ちでは接続・暗号化の成功を判定できない。
- BLESCANアドレスは引用符付き。生データは集計後に破棄する。
- GATTC Read/Notify/Indicateは長さ指定binary。payload中のCRLF/OKを応答終端にしない。
- `BLECFGMTU=0,64` は接続後にindexとsizeを指定する。引数不足のERRORを未対応判定にしない。
- `BLEGATTCPRIMSRV=0` はrole1では成功、role2で接続された状態ではERROR。GAP roleとGATT roleは別概念だが、このfirmwareの組み合わせ制限は残る。
- `SYSFLASH?` の名称列挙でmfg_nvs/fatfsが見え、ble_dataは見えなかった。内部全領域の不存在を証明するものではない。ESP-ATの任意Serverサービスにはble_data等のprovisioningが必要となる可能性があり、firmware書換え禁止の今回は進めない。

## セキュリティと状態復元

実測設定は `BLESECPARAM=8,3,16,3,3,1`、`BLEENC=0,1`。ACKだけでなくAUTHCMPLと暗号化必須Readを確認。NoInputNoOutputではMITMに対する人手確認は提供できない。対向agentは所有ESPのDevice pathのみ許可し、PIN/passkey/数値比較は拒否する。鍵保存場所・bond削除は公式仕様の調査に留め、個体鍵は取得しない。

初期SECPARAMの全0は通常のsetterで復元できず、deinit後にもRAMに残った。このため既知の `AT+RST` ソフト再起動を1回だけ実行し、ready/同版GMR/初期modeを確認。再initでSECPARAM全0・bond0を確認してBLE0へ戻した。GPIO resetや全機再起動ではない。以後のCLI試験はsecurityを変更していない。NVSへ設定保存しないよう試験時はSYSSTORE0、終了後1へ戻した。

## Linux APIと再現

独立実装 [esp32_ble.py](../../scripts/esp32_ble.py) はPython3標準ライブラリ。既存readonlyツールは変更しない。

```sh
python3 scripts/esp32_ble.py status
python3 scripts/esp32_ble.py catalog
python3 scripts/esp32_ble.py scan --seconds 2
python3 scripts/esp32_ble.py advertise --seconds 3
python3 -m unittest discover -s tests -p 'test_esp32_ble.py' -v
```

root相当のUART権限が必要。実機は`/run/t6ble`へ一時配置し、ログはVMへ保存。自動起動サービスは追加していない。

所有対向でのみ `gatt-read/gatt-write/gatt-watch --peer <owned-address> --owned-peer --service-uuid <uuid> --char-uuid <uuid>` を使う。Writeには`--data-hex`、データのprivate表示には明示的な`--include-data`が必要。通常出力はJSONでpayloadを隠す。UUIDを探索してindexを解決する。fixture serviceは `fa1c7e10-7bea-4a8e-a9f0-5f476d6a0001`、notify/read/write charは同じsuffixの`fa1c7e11`、indicateは12、暗号化必須は13。

所有対向用 [bluez_owned_gatt.py](../../scripts/bluez_owned_gatt.py) はraspi4でpython3-dbus/GIとBlueZを使う。`T6_ALLOWED_PEER`で所有ESPを指定し、`T6_GATEWAY_ADVERTISE=1`でlegacy MGMT広告を選ぶ。180秒上限。`T6_ALLOW_PAIR=1`だけが一時的な所有機器限定agentを有効化する。起動前のrfkill/powerを記録し、終了後に戻す。ログへ環境変数を出さない。

APIは `UART / AT / BLE`。共有flock、TIOCEXCL、1152008N1、termios復元、console/process使用チェック。接続とpairingは明示的所有確認、状態0から開始する。frame512byte、buffer16KiB、transaction64KiB、session256KiB、event128件を上限とし、scan1..5秒。timeout/不正frameでは同期喪失扱いで次コマンドを拒否する。安全停止を確認できない場合はBLOCKEDを出し、成功を偽らない。予期しないreadyを検出する。SIGTERM/SIGHUPと出力先切断でもcleanupを試みるが、kill -9/電源断まで保証しない。低レベルAT APIはセキュリティsandboxではなく、利用者はコマンドの影響を確認する。

## BlueZ/HCI・OpenWrt

|方式|実現性/統合|BlueZ互換|OpenWrt/工数|制約・復旧|
|---|---|---|---|---|
|A ESP-AT独立API|今回実証、Debian標準Python|HCI互換なし|Python3/termios/flockで移植、小|既存firmware維持、BLE0へ終了|
|B AT broker/API|設計候補。単一UART所有daemon+localhost Unix socket、許可操作/UUID/所有peer allowlist、期限とquota、JSON events|独自API。org.bluezの完全代替を名乗らない|procd、ubus adapter、権限制限、中|raw AT公開を避ける。Wi-Fi制御とUART排他を共有|
|C HCI専用firmware|設計のみ。ESP-IDF controller/HCI transportとLinux BT設定を別途検証|正しいHCI transport実装時のみ候補|kernel/config/firmware/復旧を含め大|現ESP-ATを置換、配線/flow control/baud・署名/復旧経路を確認する別サイクル|

C号機は現CONFIG_BT無効、ESP-AT ASCII応答でありhciattachだけで標準controllerにはならない。試験のraspi4側hci0がBlueZで動くことと混同しない。参照：[BlueZ GATT API](https://raw.githubusercontent.com/bluez/bluez/5.82/doc/org.bluez.GattCharacteristic.rst)。

## raspi4の保守・限界

不要なプロセス停止許可に基づき、wg0不在・管理経路非使用を確認したspeederv2-clientだけをstopした。disableはせず、復旧は`sudo systemctl start speederv2-client.service`。SSH、NetworkManager、NAT、UART管理は維持。RAM available約1.6GiB、42°C、throttled0、低CPU。前boot journalがなく、時間経過による不安定化の根因は特定できていない。停止後の接続継続だけで解消とは判定しない。

対向試験のためpython3-dbus/GIを導入（依存5追加、libglib関連2更新）。BCM4345C0/BlueZ5.82のD-Bus RegisterAdvertisementはInvalid Parameters 0x0dとなり、legacy MGMT広告で成功した。終了時に広告/接続/agent/applicationを解除し、元のPowered=false/rfkill soft-blockedへ復元した。全CLI3試験もBLE0 cleanup成功。

C号機最終確認：SSH/networkd/UART getty active、IPv4 ping2/2成功、CWMODE2/BLE0/SYSSTORE1。管理IP・Ethernet・UART0は変更なし。長時間連続運用、全機再起動後、最大接続数/heapリーク、Passkey/Legacy/Bond、任意ESP Server DB、Wi-Fi共存負荷は未確認。

次は別の安全な検証サイクルで、取得可能な純正ble_data定義の静的解析、firmware変更不要なServer構成の可否確認、所有peerの人手認証・bond隔離試験、長時間のSSH/電源/温度/kernelログ収集を行う。今回の範囲ではfirmware書換えをしない。
