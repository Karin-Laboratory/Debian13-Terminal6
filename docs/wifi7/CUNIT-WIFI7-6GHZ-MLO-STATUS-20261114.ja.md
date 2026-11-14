# C号機 Wi-Fi 7 / 6GHz / MLO 状況 (2026-11-14)

## 結論

| 機能 | 現在の判定 | 根拠 |
|---|---|---|
| 2.4/5GHz AP | `PARTIAL` | Debian 13上での今回の実通信・再起動復帰は未確認。RC14 OpenWrtの過去成功は別環境の結果。 |
| 6GHz AP | `BLOCKED` | 既存Debian実測ではregulatory domain `00`、6GHzチャネルは無効。対象個体の認証・運用条件も未確認。 |
| 802.11be/EHT実通信 | `NOT_TESTED` | PHY能力表示だけでは接続モードや実データ通信を証明しない。 |
| MLO実通信 | `NOT_TESTED` | 1 PHYのドライバ能力表示は、複数リンクを持つMLD接続・各リンクの通信実績ではない。 |

## 既存実機記録の基準

リポジトリのC号機記録では、Debian 13 / Linux 6.18.63でMT7990系PCI機能が列挙され、`mt7996e`系ドライバがPHYを登録している。Wi-Fi記録には2.4/5/6GHz bandとEHT能力の表示がある一方、6GHzの規制状態は`00`、チャネルは利用不可、`regulatory.db`欠落、EEPROM default-bin fallback、MCU timeoutが記録されている。Debian上のAP起動・端末通信は未試験である。

PCI ID `14c3:7990` と `14c3:7991` は、監査したLinux 6.18.63ソースのMT7996 driver内で同じ無線デバイスの本体/HIF側IDとして扱われる。2つのPCI機能は2台の独立無線機や2つの動作中PHYを意味しない。既存実機記録は単一の`phy0`を観測している。

同じカーネルソースの`mt7996/init.c`は`WIPHY_FLAG_SUPPORTS_MLO`とEMLSR能力を広告し、MLOリンク情報の管理領域を持つ。Linux Wirelessの[MediaTek driver情報](https://wireless.docs.kernel.org/en/latest/en/users/drivers/mediatek.html)も一般的なmt76機能を説明するが、この特定個体の動作証拠ではない。能力表示はC号機上でAP/STAのMLDが成立した証拠ではない。MLO PASSには、接続相手側のMLD、複数のactive link ID、各リンク上のpacket/byte増加、およびIPの双方向通信を確認する必要がある。

## 6GHzの規制ゲート

ARIB STD-T71の[公開情報](https://www.arib.or.jp/kikaku/kikaku_tushin/desc/std-t71.html)では、版8.1 (2026-10-09) が802.11be/Wi-Fi 7対応を含む。版7.0の説明は日本の6GHz帯を5925–6425 MHz、最大160 MHz幅としている。これは本機の型式認証、アンテナ構成、出力条件、設置条件、運用可能チャネルを個別に証明しない。320 MHzを許可すると解釈しない。

従って、規制ドメインを強制したり、チャネルや出力を推測設定したりしてRF送信を試すことはできない。試験前に本機の認証・許可された周波数/幅/出力と必要なregulatory databaseを確認する必要がある。

## EEPROM・firmware

既存記録では初回のEEPROM取得失敗とdriver fallbackが見られる。起動スクリプトが複数候補のファイル名を配置することだけでは、driverが選択したEEPROMが正しいことを証明できない。今回の調査では秘密・校正データを読み出したり、公開領域へコピーしたりしていない。正しいC号機OEM校正データの読取経路、選択ファイル名、適用成功ログを非公開の証拠で確認する必要がある。default-bin状態での6GHz送信は進めない。

## hostapd候補

公式hostapd 2.12ソース (SHA-256 `f43502561c28ba47ab77e18e1a973d07361c68cc8b14178e619bd5796b70eabd`) を一時作業領域で取得し、Debian arm64用に`nl80211`、802.11ax/be、SAEを有効にしてクロスビルドした。成果物はARM64 ELFで、QEMU-user上の`hostapd -v`はv2.12を返した。これはビルドと起動表示の確認のみで、C号機への配置、nl80211 AP起動、6GHz、EHT接続、MLOは試していない。バイナリと一時sysrootはgitに含めない。

## 次の実測段階

1. Storage/CQEエラーのためP44への書込み・パッケージ導入を再開する前に、担当者間でストレージ復旧と変更排他を確認する。
2. LAN/UART管理の維持を前提に、秘密情報を出さない読み取りsnapshotをDebian上で採取する。
3. regulatory database、実機の適法な運用条件、EEPROM選択とfirmware起動、MCU応答を確認する。
4. 認証/運用条件と電波試験環境が確認できてから、許可された帯域だけを低リスク段階で試験する。
5. 2.4/5GHz AP、6GHz AP、EHT接続、MLOを別々の受入項目にし、それぞれ端末接続・アドレス取得・実データ通信まで確認する。

実機への変更・再起動・RF送信は今回実施していない。
