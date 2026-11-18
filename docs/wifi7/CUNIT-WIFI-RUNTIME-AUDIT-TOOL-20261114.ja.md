# C号機 Wi-Fi読み取り専用snapshot

`scripts/cunit_wifi_runtime_audit.py`は、Wi-Fiランタイム状態を機密情報を除いて記録する読み取り専用ツール。

```sh
sudo python3 scripts/cunit_wifi_runtime_audit.py --output /run/cunit-wifi-audit.json
```

`--output`は既存ファイルを上書きせず、シンボリックリンクを拒否し、JSONをmode 0600で新規作成する。保存先はRAM上の`/run`等を使う。JSONは`iw`の生出力や`dmesg`を含まず、SSID値、MACアドレス、station識別子、EEPROM内容は出力しない。規制候補の集計にはglobal country codeだけを使い、PHYごとのself-managed表示だけでは日本のglobal設定と見なさない。

収集項目はkernel release、MT799x PCI ID/driver、regulatory country/rule、band/6GHz channel flags、EHT/MLOの能力表示、interface種別とchannel、stationのrate mode/link ID/byte counter有無、regdb/EEPROM fallback/MCU timeout/PCIe AERの有無。`iw`, `dmesg`, `uname`は参照のみで、interface作成、scan、接続、AP開始、規制状態変更、RF送信を行わない。

JSON内の`*_advertised`と`*_observed`は能力・観測値であり、法的許可や実通信PASSではない。`six_ghz_rf_start_permitted`は常にfalse。MLOのlink IDが見えただけでは、単一MLDセッション上で複数リンクが実際にpacketを運んだことにならない。

ホスト側テスト：

```sh
python3 -m unittest discover -s tests -v
```

7テストは小数表記の周波数も含め、秘密値の抑制、許可コマンドの読み取り専用性、regulatory候補の慎重な分類（globalとPHY self-managedの区別を含む）、出力の排他的作成と0600を確認する。C号機実行結果は`evidence/CUNIT-WIFI-RUNTIME-20261114.json`に保存した（個体ID・SSID・MACを含まない）。検査では小数MHz表記を整数MHzへ正規化する。
