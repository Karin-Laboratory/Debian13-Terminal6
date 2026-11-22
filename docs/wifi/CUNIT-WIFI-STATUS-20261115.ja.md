# C号機 Wi-Fi段階別ステータス (2026-11-15)

対象はC号機 Debian 13 / Linux 6.18.63、slot A。能力表示、AP起動、association、認証、IP通信は別の達成段階として記録する。

## 機能別到達状況

| 機能 | 状態 | 実機証拠 | 次の具体的な試験 / 条件 |
|---|---|---|---|
| MT7990 PCI・driver・PHY | PARTIAL | PCI 14c3:7990/7991、mt7996e / mt7996e_hif結合、phy0登録 | AP/STA実通信後にデータ経路を判定 |
| EEPROM/OTP初期化 | PARTIAL | C号機自身のOTP由来46 bytesをRAM EEPROM bufferへ統合、8/8ページACK。30秒timeout版で通常再起動後もPHY/SSH復帰 | 実通信時のfirmware・校正動作を検証 |
| 2.4GHz AP | PARTIAL | WPA2/CCMPのhostapd 2.12がstart rc=0。live iwでAP / 2412 MHz ch1 / 20 MHz / 20 dBm。TX packet counterは8秒で0から12へ増加 | clientでBeaconを受信し、association・認証・DHCP・双方向IP通信・再起動復帰を確認 |
| 2.4GHz STA | PARTIAL | 2412 MHz ch1、WPA2-PSK、DHCP予約192.168.3.32/22取得。gateway ping 3/3、外部IPv4 ping 3/3、Wi-Fi拘束TLS 1.3 / HTTP 200を確認 | DNS、再接続、通常起動後の自動復帰を確認 |
| 5GHz AP/STA | PARTIAL | channel 36 / 5180 MHz、WPA2-PSK、DHCP予約192.168.3.32/22取得。VHT 80 MHz、gateway ping 3/3、外部IPv4 ping 3/3、Wi-Fi拘束TLS 1.3 / HTTP 200を確認 | DNS、再接続、APモード、通常起動後の自動復帰を確認 |
| WPA2/WPA3-SAE / PMF | PARTIAL | 2.4/5GHz STAのWPA2-PSK handshake、IPv4、HTTPSデータ受信を確認。hostapd 2.4GHz AP start済み。WPA3-SAE/PMFは未試験 | WPA3-SAE/PMF交渉とAP側client認証を実測 |
| HE/EHT / Wi-Fi 7 | PARTIAL | C号機iw phyがAP/managed EHT iftype capabilityを表示。実association・EHT data frameなし | EHT対応client接続後、実PHY mode・双方向通信を測定 |
| 6GHz AP/STA | BLOCKED | 実効country 00。5955–7115 MHzの全チャネルdisabled。5955/5975 MHzの受動scanもInvalid argumentで開始不可。送信・認証試験なし（PSK未評価） | 適法な認証条件に対応する署名済みregdbを早期起動時に読み込み、利用可能チャネルを確認後に試験 |
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

- MACフィルタ登録前のSTA試験ではDHCPDISCOVERにDHCPOFFERが返らなかった。Wi-Fi MACの登録・DHCP予約後、2.4/5GHzで192.168.3.32/22を取得し、IPv4/TLS通信に成功した。SSID/BSSID/PSKはprivateのまま扱う。
- Wi-Fi DHCP addressは有線management subnetと重なる可能性がある。試験時はdefault routeをlan2のまま維持し、networkdのDHCP UseRoutes/UseDNSを無効にして、特定経路を事前・事後確認する。
- 2.4GHz APでclientデータ試験するには独立した接続端末が必要。
- 5GHz ch36/5180 MHzは受動beacon後にNO_IRが解除され、STA実通信を確認した。6GHz/320MHzはcountry 00でdisabledのため未送信。署名済みregdbと個体の国内認証条件が確認できるまで規制設定を変更しない。

詳細な初期化修正とprivate log参照は[PR #9](https://github.com/Karin-Laboratory/Debian13-Terminal6/pull/9)。個体固有EEPROM/OTP、SSID/BSSID、credentials、raw scan、module backupはprivate保管。

## 2026-11-16 基本機能継続試験の再開点

- このステータスのSTA証拠は、2.4/5GHzでのWPA2-PSK association、DHCP、gateway/external IPv4 ping、TLS 1.3/HTTP 200まで。DNS、意図的な切断からの再接続、通常再起動後の復帰、WPA3-SAE、速度測定はこの記録では未実施。
- AP側はhostapd起動と送信カウンタ増加まで。独立端末による外部Beacon受信、association、認証、DHCP、双方向通信、再起動復帰は未確認。今回の追加試験も行っていない。
- agent-101-vmから対象への直接経路はなく、許可済みraspi2経由のstrict SSHは接続先ホスト鍵確認後に公開鍵認証拒否となった。raspi2のUART brokerが稼働中だったためUARTも開いていない。試験中のネットワーク変更・再起動は行っていない。
- `scripts/wifi-link-check.py`を追加した。read-only既定動作でSTA association、band/frequency、WPA2/WPA3 SAE交渉、Wi-Fi経由のgateway ping、指定DNSへのDNS query、station counterを検査する。default routeが管理IFのみであることを事前確認し、経路表が不変であることを事後確認する。出力にはSSID/BSSID/MAC/IP/DNS回答を含めない。
- 明示的な`--exercise-reconnect`だけが一時的にwpa_supplicantへdisconnect/reconnectを指示する。default routeが管理IF以外を含む場合は拒否し、永続ファイル・routeを変更しない。任意の`--throughput-server`を指定した場合だけ、Wi-Fi routeを事前確認して10秒のiperf3 TCP受信速度を測る。
- オフライン合成テスト9件と既存ハードウェアツールテスト3件、Python構文検査はPASS。C号機実行、DNS/WPA3/reconnect/throughputの実測は未実施。

### 次回の実機手順

1. 既存の承認済みSSH経路を復旧し、同一bootのDebian/Linux・Ethernet管理経路をread-onlyで確認する。
2. live interface名、gateway、DNS resolverをC号機から取得し、2.4GHz/5GHzを個別にread-only smoke testする。`--security wpa2`を指定する。
3. WPA2再接続を試す場合だけ`--exercise-reconnect`を付け、管理default routeが有線に固定されていることを確認する。
4. WPA3試験は対応する既存AP/STA設定と承認済み資格情報を使い`--security sae`で交渉状態を検証する。資格情報はコマンド引数やログへ出さない。
5. 速度測定は所有者管理のiperf3 peerを指定できる場合に限る。独立peerがなければ保留する。
6. AP側試験は独立クライアントを使い、Beacon、association、DHCP、双方向通信を別々に採取する。既存のraspi4/raspi2管理Wi-Fiを試験端末に転用しない。


## 2026-11-15 STA association / DHCP follow-up

- C 2.4GHz STA completed WPA2-PSK association at 2412 MHz. 5GHz STA completed WPA2-PSK association at 5180 MHz after passive beacon discovery; effective country stayed 00 and no regulatory override was applied.
- Neither band received an IPv4 lease. During the 2.4 GHz attempt, a short C-side capture observed two DHCPDISCOVER packets and no DHCPOFFER; the 5 GHz DHCP exchange was not packet-captured. A temporary networkd file explicitly disabled DHCP routes and DNS; no IPv4 address or Wi-Fi route was installed, so wired management/default route stayed unchanged.
- No IP communication, ping, DNS, or package transfer is claimed. C wlp1s0 was returned to DOWN and all temporary credentials, supplicant files, runtime network config, and extracted package files were removed.
- Possible AP-side DHCP/client policy or a C driver/data-path issue remains unresolved. Because the AP /22 overlaps C's wired 192.168.3.0/24, no arbitrary static address was assigned.


## 2026-11-15 MACフィルタ登録後の実通信

- owner側でC号機のWi-Fi MACがMACフィルタに登録され、DHCP予約が反映された後に追試。2.4/5GHzとも同一Wi-Fi MACで192.168.3.32/22を取得し、gateway 192.168.0.1から払い出された。
- 両bandでgateway ping 3/3、外部IPv4 1.1.1.1 ping 3/3を確認。さらにwlp1s0へsocketをbindし、一時的な1.1.1.1/32経路をWi-Fi gateway経由に設定してTLS 1.3 / HTTP 200、204 response-body bytes受信を確認。DNSはこの試験で使用していない。
- 5GHzは5180 MHz、VHT 80 MHz link report。country 00は維持し、NO_IRを解除するregulatory overrideは行っていない。
- Wi-Fi試験時もdefault routeはlan2 via 192.168.3.71のまま。試験終了後に一時経路・supplicant・鍵・/run package・networkd fileを削除し、wlp1s0をDOWNへ戻した。
- 6GHzは全5955–7115 MHz channels disabled。5955/5975 MHz passive scanはInvalid argument。association/PSK試験は送信前に停止したため、提供された6GHz PSKの正誤は未判定。
