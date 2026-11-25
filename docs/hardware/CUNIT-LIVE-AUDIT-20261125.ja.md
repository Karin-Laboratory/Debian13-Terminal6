# C号機 Debian 13 UART実機監査（2026-11-25）

## 範囲と条件

対象は既存C号機。raspi3直結LANとUARTを使用した。純正slot Bから`/sbin/quec_bootctrl -F`を実行し、読み戻しでA優先、B `success=1`を確認後に再起動した。UARTでslot A、Debian 13、rootシェルまで到達した。ブートイメージ、GPT、パーティションへの書込みは行っていない。診断中に既存の`terminal6-management.service`が持つ初期化処理は起動時に一度実行済みであり、本監査から再実行していない。

実機時計は2026-04-13を示しており、依頼日と一致しない。以下の採取時刻はUARTログ内の機器時計ではなく、作業日2026-11-25のセッション記録に基づく。個体MAC、CID、シリアル、鍵、EEPROM/OTP、生ログは本公開文書に含めない。

## 起動・ストレージ

| 項目 | 実測 | 判定 |
|---|---|---|
| Slot / kernel | `bootslot=a`; Linux `6.18.63-debian-t6-proto2` | PASS |
| Debian | `/etc/debian_version=13.8` | PASS |
| rootfs | `/dev/mmcblk1p44`, ext4, rw | PASS |
| 起動引数 | `root=/dev/mmcblk0p26`; initramfs後の実rootはPARTNAME解決でP44 | PARTIAL |
| CPU / RAM | 4 CPU online; MemTotal 1,757,760 kB; MemAvailable 1,632,820 kB; swapなし | PASS |
| eMMC host | 唯一見えたhost `mmc1`, `/sys/devices/platform/11230000.mmc`; eMMC `mmc1:0001`は`mmcblk1` | PASS |
| eMMC I/O | debugfs `mmc1/ios`: requested 100 MHz, actual 94,999,965 Hz, 8-bit, HS400, 1.80 V | PASS |
| CQE / lifetime | `cmdq_en=0`; life_time `0x01 0x01`; pre-EOL `0x01` | PASS |
| エラー | `mmc1/err_stats`全項目0。採取時のdmesgにMMC timeout、I/O、ext4 errorなし | PASS |
| 稼働DTB | `/sys/firmware/fdt` SHA-256 `54ff2e7a08ba2fb45360b64862e6fcd3cdf05de13c8ec4488dbd7e0d6b5a0161`（177,338 bytes） | PARTIAL |

`mmcblk0p26`から`mmcblk1p44`への見かけ上の変化は、起動引数の初期root候補とinitramfs後の実rootの違いに加え、LinuxのMMC host列挙名が起動実装間で変わり得ることを示す。現在のhost sysfsでは`mmc1`のみを確認した。initramfsのP44検索はPARTNAMEベースである。次期実装でも`/dev/mmcblk*p44`固定ではなく、PARTNAMEとPARTUUIDの一意性を検査して選ぶこと。DT `aliases`の実測値は未採取で、列挙順が変わった根因は未確定。

## 管理LANとSSH

| 項目 | 実測 | 判定 |
|---|---|---|
| Debian管理IP | `br-lan=192.168.1.1/24` | PARTIAL |
| Port | `lan2` carrier=1、1000 Mbps/full。raspi3 eth0もcarrierあり | PARTIAL |
| SSH | Dropbearは`192.168.1.1:22`でLISTEN | PARTIAL |
| 疎通 | raspi3 eth0を`192.168.1.50/24`に設定し、明示経路でARP/ping試験。ARP解決せず、ping不達 | FAIL |
| 管理service | `terminal6-management.service` failed、ExecStart `/run/terminal6/start-management.sh` | FAIL |

起動スクリプトはchecksum確認後、`test23_netsys_fixedlink.ko`、`test23_mdio_switch.ko`、`test24_path_probe.ko`をロードし、eth1/lan2をup、lan2のcarrier/speed/duplexを確認する。続いてpath-probeの`space=3`, `reg=0x20`値を調べ、`0x31120009`以外なら制御された`phy_init`手順を一度実行し、再読出しで同値を要求する。今回のjournalには各moduleのSHAチェック成功がありserviceがstatus 1で終了した。probe valueは`0x00000000`、初期module parameterは`writes=N`、`lan2`のRXは増えていたがTXは0。スクリプト全文を照合すると、期待値不一致時は一時的に`writes=Y`として`phy_init=1`を実行する分岐があり、journalにも`phy_init` initcallがある。したがって起動時serviceが既存のwrite-enabled初期化経路を呼んだことは確認済みであり、「起動時にもMMIO書込みがなかった」とは言えない。監査者は失敗後に初期化を再実行していない。実際のregister base/addressと書込み内容はout-of-tree module source不在のため未確定。

前回のDebian起動ログでは同系scriptの初期値`0x31120008`が記録されている。別の過去実装のPCSソース`drivers/net/pcs/pcs-mtk-lynxi.c`にはMT6990 2500BASE-X設定として`regmap_write(...SGMII_MODE, 0x31120009)`とPHY reset/power sequenceがある。したがって`0x31120009`はLinux PCS実装側の設定値だが、今回のprobeの読取レジスタ`space=3, reg=0x20`と同一レジスタ/同一アドレス体系かは公開資料だけでは証明できない。`0x00000000`単独でハード故障とは判定しない。

**原因確度：** LAN packet path不成立はCONFIRMED。management serviceの失敗点はprobe値照合後の失敗経路と確認できるが、レジスタ選択、clock/reset/power domain、MAC/PCS対応、module実装のどれが根因かはUNKNOWN。次期ビルドでは試験用MMIO module/起動script依存をなくし、実測に対応するDTS (`15100000` Ethernet、PCS/SGMII、MT7531 CPU port 5、port1=LAN2)と標準phylink/PCS/DSAドライバで初期化する。受入はLAN2からCPUへのARP、双方向IP、TCP/SSHと各ポートカウンタ差分で行う。

## Wi-Fi・PCIe

| 項目 | 実測 | 判定 |
|---|---|---|
| PCIe endpoints | `14c3:7990`, `14c3:7991`が列挙、両方driver未bind | PARTIAL |
| modalias/driver | modaliasはそれぞれPCI ID 7990/7991。driver_overrideは未設定 | PARTIAL |
| modules | matching `mt76.ko`, `mt76-connac-lib.ko`, `mt7996e.ko`がP44に存在。aliasは両IDを含む | PARTIAL |
| framework | `CONFIG_CFG80211=m`, `CONFIG_MAC80211=m`; cfg80211だけロード | PARTIAL |
| firmware / PHY | `terminal6-proto2-wifi-start`は`FIRMWARE_SOURCE_NOT_FOUND_NO_P26_FORMAT_ASSUMPTION`で停止。PHYなし | FAIL |
| RF | 送信なし | NOT_TESTED |

firmware探索先は純正Bの読み取り専用root、形式が確認できた場合のP26、権限`root:0700`・SHA manifest付きowner-private領域である。いずれにも完全な4 firmwareが見つからず、スクリプトはモジュールロード前に終了する。このためfirmware不足はPHY登録失敗の直接原因だが、PCI driver未bindがfirmware不足と同一原因とは未確定。PCI IDは`mt7996e.ko`のaliasに一致するので、kernel ABI、`modules.dep`, dmesg probe、driver bind順を個別に追う必要がある。ファームウェアは個体固有/再配布条件を区別し、公開P44には権利確認済みの汎用品だけを含め、個体データは非公開seedから投入する。

## その他の機能スナップショット

| 機能 | 観測 | 判定 |
|---|---|---|
| USB | USB1/USB2 root hub。外付けdeviceなし | PARTIAL |
| Bluetooth / GNSS | `/sys/class/bluetooth`, `/sys/class/gnss`, `/dev/gnss*`なし | Linux HCI/GNSS APIはこの起動でNOT_PRESENT。物理機能の非対応は示さない |
| I2C / SPI | sysfs adapter/device一覧空 | PARTIAL |
| Thermal | 13 thermal zone、SoC max約64.9°C | PARTIAL |
| KVM | `/dev/kvm`あり | PARTIAL; このbootでguestを起動していない |
| QEMU | `qemu-system-aarch64`実行ファイルなし | NOT_TESTED |
| CPU frequency | cpufreq policy directoryなし（今回採取） | PARTIAL |
| RTC / watchdog / GPIO / PWM / buttons / LED / crypto / WWAN | 完全なAPI・実動作監査未実施 | NOT_TESTED |

## 次期ビルド反映台帳

| ID | 優先 | 問題と根拠 | 次期変更 | 受入 |
|---|---:|---|---|---|
| CU25-LAN-01 | P0 | probe値0、LAN2 ingress counter増、eth1/br-lan RX=0。起動時write-enabled `phy_init`呼出あり。exact register mapping UNKNOWN | custom module source/build identityを回収後、標準PCS/phylink/DSA/DT経路をreview | isolated ARP、bidirectional ICMP/TCP/SSH、層別counter delta |
| CU25-WIFI-01 | P1 | PCI列挙/alias/moduleあり、4 firmware不足でscriptがmodule前停止 | P44 manifest/CIで4要求名・provenance・SHAまたはprivate seed gateを必須化 | firmware load、driver bind、`iw phy`; RF送信は別承認 |
| CU25-ROOT-01 | P0 | bootargs candidate `mmcblk0p26`, mounted root P44 `mmcblk1p44` | PARTNAME/PARTUUID一意解決し、block index固定を禁止 | block enumeration variation fixtureで同一UUIDをmount |
| CU25-QEMU-01 | P2 | `/dev/kvm`あり、QEMU実行物なし | P44 package manifestへQEMU依存を追加 | isolated guest boot/virtio network |

## 証拠・制約

第二段階の追加解析、source照合、全機能反映台帳は[追補資料](CUNIT-LIVE-AUDIT-FOLLOWUP-20261125.ja.md)に記録した。

- UART wireの生バイト列は未保存。追補時に読み取り専用コマンド応答をプロンプト境界で保存したprivate tool-level transcriptがあり、SHA-256は追補資料とprivate manifestに記録した。これはraw UART captureではない。
- 稼働DTBはprivateでDTS化し、保全済みKVM成功版DTBと限定的に比較した。主要機能ノードに実質差分は見つからなかったが、完全正規化比較や他成功版との比較は未実施。
- dmesg error検索、eMMC debugfs、sysfs、systemd journal、PCI modalias/module alias、Wi-Fi scriptを確認した。
- 有線LAN再初期化、MMIO追加書込み、モジュール再ロード、RF送信、再起動、ブート書込みは行っていない。
- 公開記録の追記状態は追補資料のGitHub commitで確認する。
