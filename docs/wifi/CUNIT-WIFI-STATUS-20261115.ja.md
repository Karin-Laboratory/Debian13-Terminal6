# C号機 Wi-Fi段階別ステータス (2026-11-15)

対象はC号機 Debian 13 / Linux 6.18.63、slot A。能力表示、AP起動、association、認証、IP通信は別の達成段階として記録する。

## 機能別到達状況

| 機能 | 状態 | 実機証拠 | 次の具体的な試験 / 条件 |
|---|---|---|---|
| MT7990 PCI・driver・PHY | PARTIAL | PCI 14c3:7990/7991、mt7996e / mt7996e_hif結合、phy0登録 | AP/STA実通信後にデータ経路を判定 |
| EEPROM/OTP初期化 | PARTIAL | C号機自身のOTP由来46 bytesをRAM EEPROM bufferへ統合、8/8ページACK。30秒timeout版で通常再起動後もPHY/SSH復帰 | 実通信時のfirmware・校正動作を検証 |
| 2.4GHz AP | PARTIAL | WPA2/CCMPのhostapd 2.12がstart rc=0。live iwでAP / 2412 MHz ch1 / 20 MHz / 20 dBm。TX packet counterは8秒で0から12へ増加 | clientでBeaconを受信し、association・認証・DHCP・双方向IP通信・再起動復帰を確認 |
| 2.4GHz STA | PARTIAL | owner-managed APに2412 MHz ch1でSTA association、WPA2-PSK handshake完了。RX 68,565 bytes / 423 packets、TX 1,880 bytes / 10 packets | DHCPDISCOVERを確認したがOFFERなし。AP/DHCP経路を切り分け、IPv4通信・双方向データ・再接続を確認 |
| 5GHz AP/STA | PARTIAL | 有効な受動beacon後にchannel 36 / 5180 MHzのNO_IRなしを確認し、owner-managed APへWPA2-PSK STA association完了。RX 60,404 bytes / 454 packets、TX 1,598 bytes / 17 packets | IPv4 DHCP offerなし。APモード未試験。国別規則を強制せず、DHCP応答・IPv4通信を確認 |
| WPA2/WPA3-SAE / PMF | PARTIAL | hostapd 2.12の2.4GHz AP start、および2.4/5GHz STAのWPA2-PSK handshakeを確認。SAE/PMF交渉は未試験 | 独立clientを使うAP認証/IP試験後、SAE/PMFを別途実測 |
| HE/EHT / Wi-Fi 7 | PARTIAL | C号機iw phyがAP/managed EHT iftype capabilityを表示。実association・EHT data frameなし | EHT対応client接続後、実PHY mode・双方向通信を測定 |
| 6GHz AP/STA | BLOCKED | 起動時regulatory.db要求失敗、実効country 00。6GHzチャネルはdisabled | 署名済みregdbを早期起動時に読み込み、個体の認証・条件と利用可能チャネルを確認後に試験 |
| 160/320MHz | PARTIAL | iw phyは5GHz 160MHzと6GHz 320MHz capabilityを表示。実リンク未成立 | 許可条件とclient能力を確認し、実交渉幅を測定。320MHzは独立受入 |
| MLO | PARTIAL | 実機moduleと同じソースでWIPHY_FLAG_SUPPORTS_MLO、driver MLD link paths、最大同時links=2を確認。実際のMLD/link成立なし | 2 linkを形成し、link ID・各link counter・双方向IP dataを確認 |
| EasyMesh Controller / Agent | UNKNOWN | 1905.1 / Multi-AP接続試験なし | 実装選定後、Controller-Agent登録、topology、backhaul/fronthaul、再起動復帰 |

BLOCKEDは確認済みのチャネル制約や試験条件を示し、未搭載の判定ではない。PARTIALはコード・能力表示・AP起動までを含むが、実通信を意味しない。

## 2026-11-15 実機追試と安全状態

- raspi4の管理Wi-Fiとraspi2の既存owner-managed Wi-Fiは切り替えず、A号機は読み取り専用で確認した。C号機の接続先SSID/BSSIDは公開しない。
- Cのpassive scanは2412/2437/2462 MHzに限定し、scan後のwlp1s0 TX counterは0。2412 MHz ch1のAPを受信した。
- Cの実効規制コードは00。ch1はNO_IR/disabledなし、最大20 dBm。規制ドメインを設定変更していない。
- Debian 13 arm64 wpasupplicant 2:2.10-24を/runへ一時展開し、nl80211 driverで2.4GHzと5GHzのWPA2-PSK associationを確認。P44にはインストールしていない。利用者から提供されたPSKは試験中のroot-only /run設定にだけ使用し、公開・保存していない。
- 2.4GHz AP試験は一時WPA2/CCMP、HT20、ch1、country overrideなし、出力増加なしで8秒実施。hostapd start rc=0、live iwでtype AP / 2412 MHz / 20 dBm、TX counter 12を確認した。これはTX activityの証拠であり、外部Beacon captureやclient associationを示さない。hostapdと一時設定は停止・削除済み。
- Cは試験終了後managed / DOWN、IPv4 addressなし。wpa_supplicant、PSK設定、networkd試験ファイルを/runから削除。default routeは従来どおりlan2 via 192.168.3.71。SSHは維持。
- eMMCは100MHz上限、実クロック 94,999,965 Hz、HS400 / 8-bit / 1.80V、cmdq_en=0。mt7996eの全checksumが一致し、46 OTP bytes統合・EEPROM全8 page ACKのログを確認。新規MMC/ext4 I/O errorなし。

## 次の実通信試験

- 2.4GHz STAはWPA2 associationまで達成。DHCPDISCOVERを送信したがDHCPOFFERを受信せず、IPv4 address/data通信は未達。raspi2は同じ2.4GHz APから192.168.0.26/22・gateway 192.168.0.1をDHCP取得している。C側DHCP応答なしの原因は未解明。SSID/BSSID/PSKはprivateのまま扱う。
- Wi-Fi DHCP addressは有線management subnetと重なる可能性がある。試験時はdefault routeをlan2のまま維持し、networkdのDHCP UseRoutes/UseDNSを無効にして、特定経路を事前・事後確認する。
- 2.4GHz APでclientデータ試験するには独立した接続端末が必要。
- 5/6GHz country-specific operationには署名済みregdbの早期ロードと適用条件確認が必要。unsigned P25は適用しない。6GHz/320MHzは認証・規制条件が確認できるまで送信しない。

詳細な初期化修正とprivate log参照は[PR #9](https://github.com/Karin-Laboratory/Debian13-Terminal6/pull/9)。個体固有EEPROM/OTP、SSID/BSSID、credentials、raw scan、module backupはprivate保管。


## 2026-11-15 STA association / DHCP follow-up

- C 2.4GHz STA completed WPA2-PSK association at 2412 MHz. 5GHz STA completed WPA2-PSK association at 5180 MHz after passive beacon discovery; effective country stayed 00 and no regulatory override was applied.
- Neither band received IPv4 DHCP. A short C-side capture observed two DHCPDISCOVER packets and no DHCPOFFER. A temporary networkd file explicitly disabled DHCP routes and DNS; no IPv4 address or Wi-Fi route was installed, so wired management/default route stayed unchanged.
- No IP communication, ping, DNS, or package transfer is claimed. C wlp1s0 was returned to DOWN and all temporary credentials, supplicant files, runtime network config, and extracted package files were removed.
- Possible AP-side DHCP/client policy or a C driver/data-path issue remains unresolved. Because the AP /22 overlaps C's wired 192.168.3.0/24, no arbitrary static address was assigned.
