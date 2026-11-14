# C号機 Debian 13 ハードウェア解析（2026-11-14）

対象は所有者のAir Terminal 6、MT6990、Debian 13 arm64、Linux `6.18.63-debian-t6-proto2`。実機SSHで列挙・既知APIの読み取りを実施した。これは調査サイクルの報告であり、全機能対応・安定稼働・公開ソースだけでの再製造を保証しない。

**最優先の未解決問題はeMMCの書き込みI/Oエラー。** パッケージ導入中にCQE recoveryとext4警告、管理接続断・再起動を観測した。復旧時の小さいファイル書き込みでも再発した。管理SSHとインターネット接続は復帰しているが、rootfsの永続整合性は未確認。

## 成果物

- [総合インベントリ・ドライバ/API対応表](CUNIT-INVENTORY-API-20261114.ja.md)
- [CPU・ストレージ・Ethernet・周辺機能の詳細](CUNIT-DEVICE-DETAILS-20261114.ja.md)
- [Wi-Fi・Bluetooth・GNSS・WWAN](CUNIT-RADIOS-20261114.ja.md)
- [Device Tree解析と未知候補](CUNIT-DT-UNKNOWN-20261114.ja.md)
- [Debian / OpenWrt比較・優先順位](CUNIT-OPENWRT-DELTA-20261114.ja.md)
- [ストレージ障害・変更・復旧記録](CUNIT-STORAGE-INCIDENT-20261114.ja.md)
- [追加: CQE無効化案・EXT_CSD・純正比較](CUNIT-EMMC-MITIGATION-20261114.ja.md)
- [追加: ESP32-C3 UART/AT制御の実測](CUNIT-ESP32-C3-20261114.ja.md)
- [証拠抜粋](evidence/CUNIT-API-EXCERPTS-20261114.txt)、[DT棚卸しJSON](evidence/CUNIT-DT-INVENTORY-20261114.json)、[Kconfig抜粋](evidence/CUNIT-KCONFIG-20261114.txt)、[ツール版](evidence/CUNIT-TOOLS-20261114.txt)
- [読み取り専用収集スクリプト](../../scripts/collect-terminal6-hardware.py)、[既知API確認](../../scripts/probe-terminal6-readonly.sh)、[公開用DTメタデータ抽出](../../scripts/export-terminal6-dt.py)

追加調査でESP32-C3-MINI-1のESP-AT応答を確認した。Linux HCIは無効のままだが、外付けBLE制御へのUART経路は存在する。また、eMMCのDT単独no-CQE候補を開発VMで検証したが、実機への投入はしていない。

## 再現方法

既存の安全なSSH接続を利用し、C号機で`python3 -B -`へ収集スクリプトをstdinで渡し、stdoutを開発VMで保存する。公開collectorはメタデータのみを取得し、target側ファイル出力を拒否する。結果はまず非公開として扱い、export-terminal6-dt.pyで許可した項目を抽出後に人間/担当者が確認する。API scriptもstdoutをVMへ保存する。今回の不安定なP44へtoolをinstall・ログ保存しない。

ホスト側検査は`python3 scripts/test_hardware_tools.py`（FDT期待差分、入力SHA拒否、AT allowlist/timeout/応答上限、非公開項目除去の3テスト）を実行。4種類の実機由来DT候補のsemantic比較もPASSした。これらはホスト側検査であり、修正後eMMCのhardware PASSではない。

## 調査方法と証拠の境界

先にOS・起動引数・mount・GPT区画メタデータ・モジュール・経路・メモリ・dmesg・journal・主要sysfsを保存。APTは既存カーネルの更新を避け、`--no-upgrade --no-install-recommends`を使用した。サービスの自動起動を一時policy-rc.dで抑制し、導入処理後に撤去。GNSSやモデムの制御要求、無線送信、GPIO出力変更、watchdogのopen、未知レジスタ操作は行っていない。

生DTBにはブートローダー由来の個体情報を含むため公開しない。公開JSONは観測したDTのパス・compatible・reg等の許可したメタデータだけを再構成した棚卸しであり、元DTB/DTSやfirmwareの配布ではない。取得ログも識別子・MAC・管理接続情報・位置を除いた抜粋のみ。

VERIFIEDはその行の最小試験だけを意味する。例えばGPIOの列挙成功はピンの電気試験、温度読み取り成功は校正精度、PHY登録は無線通信を意味しない。NOT_DETECTEDは探索範囲での不検出であり、物理部品が存在しない証明ではない。

## サイクル終了時の状態

既知カテゴリA〜Hを読み取りで確認し、全DTノードの棚卸しと未バインド機能候補の分類を実施。実行できない試験は根拠付きBLOCKED/UNKNOWNとして残した。SSH・公開鍵設定・Ethernet・UART getty・IPv4 DNS疎通を確認。意図的なカーネル交換・flash・再起動・P25/P26/GPT書き込みは実施していない。既存boot-successサービスは観測された再起動時に従来の動作として実行された。

次の実機作業は、UART付きの復旧環境でeMMC I/O安定性とrootfs整合性を確認すること。稼働中rootfsへのfsck修復や推測したMMIO変更は行わない。
