# C号機 Wi-Fi段階別ステータス (2026-11-15)

対象はC号機 Debian 13 / Linux 6.18.63、slot A。これは実測済み範囲の進捗表で、未検証の無線通信を成功扱いしない。

## 機能別到達状況

| 機能 | 状態 | 実機証拠 | 次の具体的な試験 / 条件 |
|---|---|---|---|
| MT7990 PCI・driver・PHY | PARTIAL | PCI 14c3:7990/7991、mt7996e / mt7996e_hif結合、phy0登録 | AP/STA実通信後にデータ経路を判定 |
| EEPROM/OTP初期化 | PARTIAL | C号機自身のOTP由来46 bytesをRAM EEPROM bufferへ統合、8/8ページACK。30秒timeout版で通常再起動後もPHY/SSH復帰 | 実通信時のfirmware・校正動作を検証 |
| 2.4GHz AP | BLOCKED | __ap interfaceをDOWNのまま生成・削除できた。hostapd 2.12 ARM64の起動表示を確認 | 有効な規制条件、独立したクライアント、hostapd実動作を用意し認証・IP通信・再起動復帰 |
| 2.4GHz STA | BLOCKED | 現在wlp1s0 managed / DOWN、TX packet counter 0 | 管理回線に影響しない独立したAP/クライアントと適法な設定で接続・通信 |
| 5GHz AP/STA | BLOCKED | capabilityの表示のみ。RF試験なし | 適法な非DFS/DFS条件と別クライアントを用意し、帯域幅・暗号・IP通信を実測 |
| WPA2/WPA3-SAE / PMF | UNKNOWN | hostapdの機能を含むビルドはあるが、接続試験なし | 実クライアントとの認証ネゴシエーションを記録 |
| HE/EHT / Wi-Fi 7 | UNKNOWN | iw phyの能力表示のみ | EHT対応クライアントとassociation後、実際のPHYモード・双方向通信を測定 |
| 6GHz AP/STA | BLOCKED | 起動時regulatory.db要求失敗、実効country 00。6GHzチャネルは利用可能と確認できていない | 署名済みregdbを早期起動時に読み込み、個体の認証・条件と利用可能チャネルを確認後に試験 |
| 160/320MHz | UNKNOWN | 実リンク未成立。チャネル幅の広告は実対応の証拠ではない | 許可条件とクライアント能力を確認し、実交渉幅を測定。320MHzは独立受入 |
| MLO | UNKNOWN | 独立phyは1基。7990/7991のendpointを別PHYとは扱っていない | radio/link構成を確認し、MLDのlink ID、各link counter、実IP通信を確認 |
| EasyMesh Controller / Agent | UNKNOWN | 1905.1 / Multi-AP接続試験なし | 実装選定後、Controller-Agent登録、topology、backhaul/fronthaul、再起動復帰 |

BLOCKEDは今回の実機証拠だけに基づく再開条件を示す。ここでの表は未搭載の判定ではない。

## 2026-11-15 最終安全状態確認

- /usr/lib/modules/6.18.63-debian-t6-proto2/updates/terminal6-mt76/MODULE-SHA256SUMSの3モジュールをC号機上で検証し、すべてOK。mt7996e.ko SHA256は c87f66f6573d5a4c3d1e829009fc42baf3223f1b0b958c4fc8a549b135e0fecd。
- wlp1s0 は managed / DOWN、TX/RX counter 0。AP interfaceなし、hostapd daemonなし。hostapdと候補moduleの一時ファイルは /run に残っていない。
- 起動ログに merged 46 OTP calibration-free bytes into EEPROM buffer および uploaded all 8 EEPROM buffer pages があり、その後の採取ログにEFUSE_CTRL timeout、EEPROM page失敗、MMC/ext4 I/O errorはなかった。
- eMMCは上限100MHz、実クロック 94,999,965 Hz、HS400 / 8-bit / 1.80V、cmdq_en=0。C号機SSHはraspi4経由で接続できた。
- この確認ではRF送信、スキャン、association、AP/STA、Beaconを開始していない。hostapdは /run 上の -v 確認に限り、P44へは導入していない。

## 再開条件

次の実通信試験には、(1) 起動時に利用可能な署名済みregulatory databaseを組み込んだ正規署名済みP25（既存署名の流用不可）、(2) 適用法令・機器認証に沿った国・チャネル・帯域幅・出力条件、(3) 管理経路を切り離さず使える独立したWi-FiクライアントまたはAPが必要。P25署名と検証済み復旧経路を満たすまでinitramfs候補を実機起動せず、許可条件が確認されるまでBeaconやprobe等の送信を行わない。

既知の実機修正・再起動結果・rollbackは[PR #9の詳細記録](https://github.com/Karin-Laboratory/Debian13-Terminal6/pull/9)を参照。個体固有EEPROM/OTP、raw log、module backupはprivate保管。
