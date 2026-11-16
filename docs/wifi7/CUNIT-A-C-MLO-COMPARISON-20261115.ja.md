# C号機 Wi-Fi 7 MLO比較・進捗 (2026-11-15)

## 判定

**5GHz 160MHz + 6GHz 160MHz MLOの実装・通信は未達。** 今回新たなA/C実機操作は行っていない。C号機の許可済みraspi2経由接続はSSH公開鍵認証で拒否され、UARTデバイスもraspi2上で見つからなかった。A号機は読み取り専用を守り、既存PR #6の保存済み観測を比較根拠にした。

| 項目 | 証拠・判定 |
|---|---|
| A号機のMLO | 未実証。保存観測では純正`mt_wifi`/MT7990、`phy0/1/2`が各2.4/5/6GHzを示し、6GHz AP設定の一部が6075MHz/320MHz。観測時の接続端末はなし。AP設定・能力表示はMLD接続や通信の証拠ではない。 |
| C号機のMLO | 未実証。Linux 6.18.63の`mt7996e`が単一wiphy `phy0`を登録した記録はあるが、per-radio inventoryは未採取。 |
| C 2.4GHz/5GHz STA | PR #9の保存実測では、両帯域でSTA接続、DHCP、gateway/external ping、TLS 1.3/HTTP 200を確認。5GHzは5180MHz、VHT 80MHz。これはMLO/APの実証ではない。 |
| C AP | PR #9で2.4GHz hostapd起動とTX counter増加のみ。外部Beacon受信、client認証、DHCP/IP通信は未確認。 |
| C 6GHz | BLOCKED。保存観測ではglobal regulatory code `00`、全6GHzチャネルdisabled。対象C号機ラベルと認証条件、規制DBの適用状態が未確定。6GHz送信・認証は行わない。 |
| 320MHz | 本目標では使用しない。A号機の設定をC号機へ転用しない。 |

## A/Cの実装差

### A号機 (保存済み読取記録)

PR #6に記録された純正環境はLinux 5.4.238、独自`mt_wifi`/MT7990ドライバおよび純正firmware。`phy2`に6GHz、`phy1`に5GHz、`phy0`に2.4GHzが報告され、`iw dev`のサンプルには6075MHz/320MHz設定のAPがあった。サンプル時点で関連STAは接続していなかった。記録にはMLD、複数link ID、per-link packet counterまたは双方向IP通信がない。従ってA号機も今回の証拠範囲ではMLO実動作未確認である。

このA号機設定値は、C号機の許可されたチャネル幅・出力条件を示さない。Cの設定雛形や規制上の根拠として複製しない。

### C号機 (保存済みDebian 13/Linux 6.18.63記録)

PR #6/#9の証拠では、PCI ID `14c3:7990`と`14c3:7991`がLinuxのMT7996-family driverに結合し、単一wiphy `phy0`が2.4/5/6GHz/EHT能力を示した。これら2つのPCI functionは2台の独立した無線機や2本のMLO linkを意味しない。

PR #9はEEPROM/OTP初期化timeout修正後の2.4GHzおよび5GHz STA実通信を記録する。6GHzについてはcountry `00`およびdisabled channelが残るため、RF試験は未実施。6GHzを使う場合は、C号機の個体ラベル、認証条件、屋内/屋外条件、許可されたチャネル・電力、および署名付きregulatory DBの起動時適用を確認して別ゲートを満たす必要がある。

## ドライバと無線構成の静的解析

参照ソース: `/home/masataka/private/debian13-proto3-build-20261112/kernel` (Linux v6.18.63 build inputs、stable source commit `1cdda838e8475edf89b73ff0cc952005dd0b1fa7`)。ソースは実機状態の証明ではない。

- `mt7996.h:14,389-391`は`MT7996_MAX_RADIOS=3`、`struct mt7996_dev`の`radio_phy[]`、`radios[]`、`radio_freqs[]`を定義する。
- `init.c:415-455`の`mt7996_init_wiphy_band()`は、登録されたband/phyについてwiphy radio frequency rangeを構成する。5GHz rangeは5.0–5.9GHz、他の分岐は2.4GHzおよび6GHz rangeを登録する。
- `init.c:86-102`はAP/STA MLD capabilityの最大simultaneous linksを`MT7996_MAX_RADIOS - 1`として広告する。これは能力advertisementであり、個体に2本の要求bandが同時に割り当て可能、または稼働中であることを示さない。
- `init.c:27-34`のglobal interface combinationは3 different channelsを広告するが、firmware、校正、regulatory、物理frontend、thermal/RF coexistence、同時160MHz運用が成功する保証ではない。
- このソースは`init.c:507-508`で`WIPHY_FLAG_SUPPORTS_MLO`を立てている。一方、現行kernel cfg80211 API文書はこのflagをMLO API向けのtemporary gateと説明し、complete feature/interface-combination advertisementが揃うまで通常driverは立てないよう記載する。これはAPI成熟度への注意であり、このdriverの実機動作が必ず失敗するという証明ではない。flagだけをMLO readinessの判定に使わない。
- 本作業で得たC号機live `iw phy`出力には`Radios:`節が含まれていないため、5GHzと6GHzが同一/別radioへどう対応するかはUNKNOWN。`iw dev`の`phy#N`はwiphy indexであり、radio IDとは同一視しない。

## hostapd / client条件

公式hostapd 2.12のソース・設定構文にMLD関連項目があること、およびARM64候補をQEMU-userで起動できた記録はPR #6に残る。ただし、2リンクを異なるband/radioへ結びつける実機構成、link ID割当、C号機driverとの互換性は未確定であり、当て推量のhostapd設定を開始しない。

クライアント側も802.11be MLO対応STAが必要。過去に使ったIntel AX201はWi-Fi 6世代であり、2リンクMLOの受入端末にはならない。対応端末と同一のMLD associationを確認するまでは、AP能力表示だけで合格にしない。

## このブランチの監査ツール変更

`scripts/cunit_wifi_runtime_audit.py`は読み取り専用の出力から、`iw dev`のinterfaceごとのwiphy indexと、`iw phy`が提供する場合のper-radio frequency inventoryを記録する。band/frequency/channel concurrencyの広告値を実動作やRF許可と誤認しないよう、`radio_inventory_available`を明示し、inventory不在を推測で埋めない。

既存テストで`iw phy`の小数MHz表記（例 `5955.0 MHz`）が6GHz channel parserから落ちる不具合を検出し、小数表記を受け入れるよう修正した。ツールはMAC/SSIDを出力せず、radio操作コマンドを実行しない。

## 次の段階

1. C号機storageとアクセス経路が安定した後、読み取り専用で`iw phy`の`Radios:`節を取得し、band-to-radio対応を確認する。
2. 実際の許可条件を証明するまで6GHz RFを開始しない。規制DB適用と正確な機器ラベル/認証条件が別ゲート。
3. 5GHz単独AP/STAの通信試験を行い、160MHzが許可される条件とclient能力を別々に記録する。
4. 802.11be MLO対応STAを用意し、2.4/5/6GHzの実測radio topologyとhostapd/kernel対応に基づいてMLD構成を決定する。
5. RF gateが満たされれば5GHz 160MHz + 6GHz 160MHzを別々のlinkとして設定し、両linkのassociation、160MHz width、per-link TX/RX増加、双方向IP通信を実証する。
6. link停止/復帰、性能、遅延、再送率、再起動後復帰を確認する。A号機は読み取り専用の比較を維持する。

## 今回の実機操作

新たなA号機またはC号機への操作、RF送信、設定変更、再起動、モジュール差し替えは行っていない。許可されたraspi2経由のC号機公開鍵SSHは拒否され、raspi2上にUART device nodeは見つからなかったため、今回の状態を新規live measurementとは主張しない。raspi4や別経路からの接続で制限を迂回していない。

## 参照

- [PR #6: C-unit Wi-Fi 7/6GHz audit](https://github.com/Karin-Laboratory/Debian13-Terminal6/pull/6)
- [PR #9: MT7996 EEPROM/OTP and STA tests](https://github.com/Karin-Laboratory/Debian13-Terminal6/pull/9)
- [Linux Wireless MediaTek driver information](https://wireless.docs.kernel.org/en/latest/en/users/drivers/mediatek.html)
- [Linux cfg80211 documentation](https://docs.kernel.org/driver-api/80211/cfg80211.html)
- [ARIB STD-T71](https://www.arib.or.jp/kikaku/kikaku_tushin/desc/std-t71.html)
