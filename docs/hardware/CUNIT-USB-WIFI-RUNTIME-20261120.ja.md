# C号機 USB・内蔵Wi-Fi 実機状況（2026-11-20）

## 目的と安全境界

本記録は、C号機のDebian 13実機でUSBホストと内蔵Wi-Fiを確認した結果を、ハードウェア認識・ドライバ登録・入出力の段階に分けて残す。対象カーネルは `6.18.63-debian-t6-proto2`。過去の別イメージでの成功と、今回のKVM成功版での実測を区別する。

試験中にP25/P26、GPT、boot control、P44の永続ファイル、純正slot Bは変更していない。再起動・slot切替・RF送信もしていない。USBモジュールは `/run` から試験ロードし、P44へインストールしていない。純正Bのrootfsは短時間 `ro,nosuid,nodev,noexec` で読み取り専用マウントしてfirmwareの存在だけを確認し、アンマウント済み。

## 実機基準状態

- Debian 13.7、kernel `6.18.63-debian-t6-proto2`、slot A、P44 ext4 rootで稼働。
- 管理Ethernet/SSHは試験前後に維持。raspi4からのpingは3/3成功。
- `/dev/kvm` は存在。試験時にQEMUゲストは起動していなかった。
- 試験後のdmesg検索で、新規のMMC I/O、ext4、DATA TIMEOUT、CQE recoveryエラーは見つからなかった。

## USBホスト

### 構成と実装

実機Device Tree/sysfs上でMTU3 dual-role controller (`11201000.usb`)、配下のMediaTek xHCI (`11200000.xhci0`)、USB PHY (`mtk-xsphy`) を確認した。稼働カーネルでは `CONFIG_USB=m`、`CONFIG_USB_XHCI_HCD=m`、`CONFIG_USB_MTU3=m`。未ロード状態ではUSB busが存在しなかったため、同じkernel releaseを対象にした既存のPR #7試験ビルドから、次の依存順で `/run` に置いたモジュールをロードした。

`usb-common` → `roles` → `extcon-core` → `usbcore` → `udc-core` → `xhci-hcd` → `xhci-mtk-hcd` → `mtu3`

すべての挿入に成功し、controller probeは0を返した。xHCIがUSB 2.0/USB 3.xのroot hubを登録し、`lsusb` でLinux Foundation root hubの2基が見えた。xHCIログはUSB 3.2 Enhanced SuperSpeed対応、MTU3はSuperSpeedPlus能力を報告した。これはcontrollerの能力・root hub登録であり、外付け機器の速度測定ではない。

試験モジュールは既存のPR #7由来build treeで作成し、稼働kernelと同じrelease名のvermagic、USB関連config subsetの一致を確認してから一時ロードした。build treeと実機kernelのbuild ID/`Module.symvers`が同一だとは確認できていない。一方で当該モジュール一式は今回の実機で実際にロード・probe成功した。`CONFIG_MODVERSIONS`は無効。今後P44へ永続配置する前に、対応するbuild provenanceを確定する。

### 判定

| 段階 | 結果 | 根拠・制限 |
|---|---|---|
| USB host/PHY DTノード確認 | PASS | 実機DT/sysfsでcontrollerとPHYを確認 |
| xHCI/MTU3 driver bind | PASS | 試験ロード後に両driverがbind、probe成功 |
| USB 2/3 root hub登録 | PASS | `lsusb` にroot hub 2基、sysfs `usb1`/`usb2` |
| downstream USB device列挙 | NOT_TESTED | 試験中に外部USB機器が接続されていなかった |
| 外部機器の実データ入出力 | NOT_TESTED | 対向USB機器なし |
| hotplug・切断後復帰 | NOT_TESTED | 対向機器なし |
| 外部ポートVBUS給電 | NOT_VERIFIED | probe時に `vbus`/`vusb33` regulatorが見つからずdummy regulatorへfallback。給電を試していない |
| 永続化 | NOT_TESTED | モジュールはP44に配置せず、起動時自動ロードも未設定 |

従って、今回の実用上の前進はDebian上でUSB host controllerとroot hubを実際に登録できたこと。外部USB機器の機能受入は未完了である。外部機器を接続する次回試験では、非ストレージの既知USB機器から始め、VBUS条件を別途確認する。

## 内蔵Wi-Fi

### 実機で確認した状態

- PCIe列挙でMediaTek `14c3:7990` と `14c3:7991` の無線endpointを確認。どちらも試験時点でdriver unbound。
- `iw dev` は `nl80211 not found`。PHY/interfaceは登録されていない。
- 実行中カーネル設定は `# CONFIG_CFG80211 is not set`。`mac80211` も有効化されていない。したがってLinux wireless APIがなく、現在P44にある `mt76` / `mt76-connac-lib` / `mt7996e` だけでは動作条件を満たさない。Wi-Fiモジュールはロードしていない。
- P44のfirmware領域ではMediaTek MT7990用firmwareを確認できなかった。個体の純正slot B rootfsを読み取り専用で調べると、MT7990 firmware群とEEPROMファイルが存在した。ファイル内容や個体固有calibrationは読み出し・コピー・公開していない。
- 6GHz band、チャネル、PHY、interface、無線通信は今回のDebianで未確認。RF送信は実施していない。

### 判定

| 段階 | 結果 | 根拠・制限 |
|---|---|---|
| PCIe endpoint認識 | PASS | `14c3:7990`、`14c3:7991` を列挙 |
| Wi-Fi driver bind | FAIL | endpointはunbound。稼働kernelにcfg80211/mac80211がない |
| PHY/interface登録 | FAIL | `iw dev` が `nl80211 not found` |
| firmware/EEPROM初期化 | NOT_TESTED | driver probe未実施。P44に必要firmwareがなく、純正Bのfirmwareは存在確認のみ |
| 2.4/5/6GHz capability | NOT_TESTED | PHY未登録 |
| RF通信 | NOT_TESTED | RF送信なし |

過去のPR #9にある2.4/5GHz STA・AP実績は別のDebian候補とそのdriver構成での履歴であり、今回のKVM成功P25でのPASSとは扱わない。PR #7のUSB試験記録も過去実績として参照し、今回の試験ロードと区別する。

## 安全な次工程

現行P25を維持してWi-Fiを有効化するには、少なくともcfg80211/mac80211を含むkernelと、同一ビルド・設定・symbol ABIに合わせたmt76/mt7996eモジュール群が必要。単に現在の `mt7996e.ko` のvermagicが一致するだけでは互換性を証明しない。今回確認した既存ホストbuild treeは無線APIを有効にしているが、稼働P25と同一のkernel build ID/Module.symversである証拠がなく、実機へロードしなかった。

推奨する次作業は、起動成功P25の正確なソース/config/build provenanceを確定し、成功版を変えない別candidateでwireless stackとdriverを一体ビルドし、modversion/exports/firmware要求を検証すること。その候補の署名・実機書込み・再起動は既存の個別安全ゲートに従う。純正Bのfirmware/EEPROMをDebianで使う場合も、再配布せずC号機内の適法な導入・保管経路を別途設計する。無線送信は認証・国内規制・regdb・試験条件が確認されるまで行わない。

## 記録

生ログと一時モジュールはraspi4の非公開作業領域に保存した。公開文書には個体固有識別子、MAC、EEPROM内容、秘密情報、firmware本体、内部の保存パスを含めない。記録更新後はこのファイルのPR上の読み戻しを行う。

関連する過去資料：

- [ハードウェア調査一覧](README.md)
- [MT7996 EEPROM/OTP初期化の2026-11-15実測](../wifi/CUNIT-MT7996-EEPROM-CALIBRATION-20261115.ja.md)
- [過去のUSB host runbook PR #7](https://github.com/Karin-Laboratory/Debian13-Terminal6/pull/7)
- [過去のWi-Fi初期化PR #9](https://github.com/Karin-Laboratory/Debian13-Terminal6/pull/9)
