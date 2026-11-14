# C号機 Debian 13 内蔵モデム読み取り専用調査（2026-11-14）

## 範囲と判定

対象はC号機のslot A、Debian 13、Linux `6.18.63-debian-t6-proto2`。raspi4経由の既存strict SSHで観測した。所有者によれば挿入SIMはpovo。ただし、今回SIMの認識、ICCID、網登録、APN、通信は一切問い合わせていない。BLEの並行作業と競合しないようUART、ttyS1、ESP32には触れていない。実機への書込み、サービス起動、modemコマンド、再起動、パーティション読出しはしていない。匿名化前の観測原本はowner-privateのraspi4 `private/cunit-modem-readonly-20261114/live-inventory.private.log`に保管した。

**結論:** カーネルのCCCI/DPMAIF/MEDMCU基盤と21個の`ccmni`は存在するが、MD1はFSM `INVALID`、ユーザー空間モデム起動処理は存在せず、モデムREADY・SIM認識・LTE/NR登録・データ通信は未到達。povo SIMの挿入は利用可能性の証明ではない。

| 層 | Debian実測 | 判定 |
| --- | --- | --- |
| 起動環境 | Debian 13、slot A、P44 ext4 RW、管理SSH継続 | 確認 |
| kernel config | CCCI/CCIF/DPMAIF/CCMNI/MEDMCU/RPMSG有効 | 確認 |
| platform | `ccci_hif_dpmaif`、`ccci_hif_ccif`、`medmcu` bind | 確認 |
| CCCI制御口 | `/dev/ccci_*`多数、`ttyCMBIM`などのノードあり | ノードのみ確認。名称から標準MBIM対応は推定しない |
| MD1 FSM | `/sys/kernel/ccci/boot`は`md1:0` | ソースの`CCCI_FSM_INVALID=0`に対応。READYではない |
| netdev | `ccmni0..20`の21個、全てDOWN、RX/TX 0 | データ経路未起動 |
| userspace | `ccci_mdinit`、FSD、RPCD、NVRAM、MIPC、RILの稼働プロセス／systemd unitなし | 初期化経路未移植 |
| カーネルログ | CCCI port登録、DPMAIF probe、MEDMCU probeを確認。HS1/HS2/READYなし | bindとMD起動は別 |
| SIM / povo / LTE / NR | 問い合わせなし | 未確認 |

`/sys/kernel/ccci/boot`のshowは`ccci_modem.c`の`boot_md_show()`経由で`ccci_fsm_get_md_state()`を数値表示する。該当ソースの`ccci_fsm_internal.h`で0は`CCCI_FSM_INVALID`、3が`CCCI_FSM_READY`。同属性のstoreは内部`boot_md_store()`が`-EACCES`を返すため、属性への書込みを起動手順と見なせない。今回は書込みを試していない。`CCCI_IOC_DO_START_MD`は現在configで無効化されていない`CONFIG_MTK_ECCCI_NO_MDINIT`の分岐により、呼び出しプロセス名が`ccci_mdinit`であることを要求する。汎用WWANデーモンを直接起動すればMDが始まる構造ではない。

## 純正と過去の成功例との差

C号機保存済み純正rootfsの起動スクリプトには`1nvram_daemon`、`2ccci_fsd`、`3ccci_mdinit`（`/usr/bin/ccci_mdinit 0`）、MIPC/WANサービスがある。これらはP44 Debian上にない。純正の各daemonはNVRAMやモデムFSへ書き得るため、読み取り専用の本工程では実行していない。ファームウェア投入、NVRAM ready、MD start、HS1/HS2、MIPC、SIM確認、PDN、IP設定の順を実測で一つずつ確立する必要がある。現時点で最初の未達は**ユーザー空間のMD起動前**。

2026-10-22の**B号機Test26+**ではRAM隔離OpenWrtでMD READY、SIM READY、povo APNのdata-call戻り値0まで観測したが、`ccmni` RX=0、ping失敗で、IP実通信の成功ではない。後続Test36-Aでは`ccci_mdinit`がNVRAM ready待ち、MEDMCU bind不成立のためMD READY未達だった。今回C号機のMEDMCU bindはTest36-Aより前進しているが、ユーザー空間とMD FSMは未起動。

2026-09-26〜27の別の実験機の**純正ファームウェア**ではpovo/KDDI LTE登録、IPv4 PDP、DNS/ping/HTTPSに成功した。物理C号機・Debianでの成功証拠ではない。NRはその記録でも一時的な活動のみで、安定した5G登録を証明しない。SIMとファームウェアが同一かも今回未確認。

## 制御APIと実装境界

| 経路 | ソース・実体 | 今回の意味 |
| --- | --- | --- |
| MD状態 | `drivers/misc/mediatek/eccci/ccci_modem.c`、`fsm/ccci_fsm_internal.h` | FSM数値の読み取り。現状0 |
| MD開始 | `fsm/ccci_fsm_ioctl.c`、`CCCI_IOC_DO_START_MD` | `ccci_mdinit`の実行環境・前提が必要。未実行 |
| CCCI port | `drivers/misc/mediatek/eccci/port/` | ttyCMBIM/FS/RPC/IPC等のカーネル口のみ存在 |
| データプレーン | `hif/ccci_hif_dpmaif.c`、`port/port_net.c` | `ccmni`登録のみ。IP packetは未観測 |
| MEDMCU | `drivers/misc/mediatek/`のMEDMCU実装、sysfs driver link | platform probe済み。modem readyとは別 |

保存済みカーネルツリーはowner-privateの`debian13-proto3-build-20261112/kernel`。上記判断は同ツリーの`.config`、`ccci_util_lib_sys.c`、`ccci_modem.c`、`ccci_fsm_ioctl.c`、`ccci_fsm_internal.h`とC号機のライブ状態を照合したもの。実行中Imageと保存ツリーの完全なソース再現性は今回の読み取り専用監査では別途証明していない。

## 次の開発ゲート

1. 純正C号機rootfsのdaemon依存、ABI、NVRAM/FSDの読み書き先、device-node契約、FWロード元・ハッシュをオフラインで固定する。OEMバイナリを公開GitHubへ移さない。
2. C号機の現行MD1がINVALIDになる起動時系列を、既存private UART/bootログと一致させる。`get scp-sys-md1-main failed`等のログは原因候補であり、単独で断定しない。
3. 実機を変更する別工程では、復旧経路とOEM領域保全を確認し、MD start→HS1→HS2→READYを独立判定する。READY以前にSIM/PDNを操作しない。
4. READY後に初めてpovo SIM認識、KDDI網登録、LTE/NR種別、APN、PDN、`ccmni`双方向パケットを測る。データ-call成功値と通信成功を分ける。

NR能力は純正実験機の断続的観測と製品構成からの候補にとどまる。C号機DebianではNR信号・網登録・データ経路の証拠がない。USB標準MBIM/QMI、PCIeモデム、一般的なModemManagerによる自動対応も証明されていない。

### 判定

`CCCI_KERNEL_ENUMERATION=PASS`、`MEDMCU_PLATFORM_BIND=PASS`、`MODEM_READY=NOT_OBSERVED`、`POVO_SIM_RECOGNITION=NOT_TESTED`、`LTE_DATA=NOT_TESTED`、`NR_5G=NOT_TESTED`。次の最小証拠は、安全な実機起動工程での`ccci_mdinit`前提充足とFSM READY遷移の観測である。本工程の作業終了時点で管理SSHは継続していた。
