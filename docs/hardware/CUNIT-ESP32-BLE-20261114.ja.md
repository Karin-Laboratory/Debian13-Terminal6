# C号機 ESP32-C3 BLE実機解析（2026-11-14）

既存UART報告の追加調査。ESP-AT 3.1.0.0-dev / MINI-1。最新mainと未マージPR #3の追記を読み、稼働C号機のcmdq_en=0を読み取り確認した。今回kernel/firmware/GPIO resetは変更していない。

## 実測チェックポイント

- AT+CMD?で168件のcommand登録と対応形式を取得。広告された形式と実際の成功は区別する。
- BLEINIT=1/2の初期化とBLEINIT=0の終了・readbackが成功。
- 2秒のpassive scan: 39 reports、11 unique addresses、RSSI -80〜-50 dBm。生アドレス・広告payloadは公開しない。
- nonconnectable advertisingを3秒で開始/停止、正常終了。さらに所有者のraspi4を対向としたconnectable advertisingで無線接続を確認。
- ESP32 Central / GATT Clientとraspi4の独立したcustom-UUID GATT Serverで接続成功。15 bytesのNUL/改行入りfixture Read、16 bytes Write・Readback一致、Notification 3件、MTU64、切断とBLE0復帰を確認。
- ESP32ローカルGATT Serverは作成/開始がOKを返すが、UUID queryが0xだけとなりcharacteristic queryはERROR。現firmwareの制約を解析中であり、custom GATT Server実装成功とはしない。
- 周辺の未知機器への接続・pairingはしていない。

raspi4のBLEは最初soft-blockedだったため試験用に解除。D-Bus RegisterAdvertisementではInvalid Parametersとなったが、所有adapterのlegacy MGMT advertising経路で接続できた。終了時に元のpower/rfkill状態を復元する。

## raspi4調査

管理経路に使っていないspeederv2-clientだけを停止（再起動時のenable状態は変更せず）。当時RAM available約1.6GiB、温度42°C、throttled=0。前boot journalは保持されず、停止が不安定化の原因を解消したとの証明はない。対向GATT試験に必要なpython3-dbus/GIを導入。

後続コミットで制御API、パーサ/timeout/privacyテスト、command対応表、Indication・security・再接続結果と復元状態をこの文書へまとめる。
