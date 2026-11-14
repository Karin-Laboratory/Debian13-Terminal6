# C号機 Debian 13 実機調査チェックポイント（2026-11-14）

実機SSHによる非破壊調査。カーネルは6.18.63-debian-t6-proto2。これは汎用インストーラや完全なハードウェア対応宣言ではない。

- rootはP44 ext4 RW、4コアARM Cortex-A55、MemTotal 1,757,596 KiB。
- 稼働Device Tree 881ノード、明示disabled 3ノード。platform 335件中driver symlinkあり40件、なし295件。未バインド件数は物理部品数や不具合数ではない。
- PCIはMediaTek root port 2件と14c3:7990 / 7991の計4件。mt7996e / mt7996e_hifにバインド。
- MT7531のMDIO列挙、lan2 1Gbps full duplex、DSA/mtk_soc_eth、SSH・IPv4疎通を確認。
- cfg80211のphy0は登録済み。AP/STAを広告するが、DebianでAP接続は未試験。6GHzはチャネルdisabled。MCU timeoutがありWi-Fi通信成功とはしない。
- CONFIG_BT未設定、AF_BLUETOOTHでerrno 97、HCI未登録。CONFIG_GNSS未設定、GNSS標準デバイス未登録。
- 21個のccmniとCCCI制御ノードは列挙。WWANのデータ通信・SIM状態は未検証。
- 13個のthermal zoneは温度値を返した。ただし校正データのnvmem取得警告があり、絶対温度精度は未検証。

## 重大な制約

追加ツール導入の書き込み中にDATA TIMEOUT ERR、CQE recovery、P44 I/O errorとext4 unwritten extent変換失敗を記録し、管理接続喪失と再起動を観測した。直接の再起動原因は未確定。カーネル交換・意図的な再起動・ストレス再現は行っていない。

再起動後にSSH/default/DNSが復帰し、dpkg --configure -aは終了0。パッケージ整合性検査により新規導入ファイル2件の破損が判明したため、保持済み同版debのチェックサムで検証して限定復旧を試みたが、syncがI/O errorを返した。後続の読み取り検査は一致しても永続修復は未確認。大容量書き込み試験はBLOCKEDとする。

続報: [eMMC限定試験・CQE無効化候補](CUNIT-EMMC-STABILITY-20261114.ja.md)でP44の退避、4KiB〜16MiBの段階書込み、APT小容量パッケージ導入、単回再起動後のSHA/SSH確認を実施した。今回の試験範囲では新たなMMCエラーなし。CQE off候補は未署名・未実機適用であり、根本原因確定や大容量書込みの一般的安定性宣言ではない。[ESP32-C3 UART1実測](CUNIT-ESP32-20261114.ja.md)も参照。

再起動をまたいでeMMC名がmmcblk0からmmcblk1へ変化した。デバイス番号を固定せず、PARTNAME・sysfsのコントローラ経路・現在のrootマウントを照合する必要がある。

生DTB、校正情報、固有ID、管理ネットワーク情報、位置、純正バイナリは公開しない。最終インベントリ・API対応表・再現スクリプト・OpenWrt差分は後続の同ディレクトリ文書へ追記する。

## 最終資料と追加調査

[総合解析の成果物・制約・再現手順](README.md)へ整理した。追加のESP32-C3 AT照会は成功し、eMMCのDT単独no-CQE候補を含む4案は開発VM上のsemantic検査を通過。実機への修正投入・P44負荷試験はしていない。P44のI/O不安定性は未解決。
