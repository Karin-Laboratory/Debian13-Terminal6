# C号機 Debian 13: MT6990 GNSS移植進捗 (2026-11-20)

## 判定

**GNSS測位・航法データ取得: NOT_TESTED (Debian)。**

現行DebianにはMT6990 GPSのDevice Tree nodeが存在するが、platform deviceへドライバはbindしていない。GNSS class/device nodeもなく、実データ・衛星捕捉・測位・航法メッセージは確認していない。純正B号機のGNSS成功実績をDebianの実績として扱わない。

この作業では、C号機の稼働中P25/P44、slot、boot control、GPT、GNSS制御状態を変更していない。P44へのファイル配置、モジュールロード、GNSS firmware要求、電源/clock/reset操作、NMEA/GNSS endpoint読み書き、再起動は未実施。

## 既存の到達点と今回の読み取り専用確認

対象はC号機 `terminal6-debian`、Debian 13.7、Linux `6.18.63-debian-t6-proto2`。実測時点でslot A、rootは`/dev/mmcblk0p44` ext4。管理SSHはraspi4から既知host keyを指定して成功した。

| 段階 | 状態 | 根拠 |
|---|---|---|
| DT platform device | PASS | `/sys/bus/platform/devices/18000000.gps`、modalias `of:NgpsT(null)Cmediatek,mt6990-gps` |
| ドライバbind | FAIL (現状) | `driver` symlinkなし |
| GNSS kernel API/device | FAIL (現状) | `CONFIG_GNSS`未設定、`/sys/class/gnss`・`/dev/gps*`・`/dev/gnss*`なし |
| firmware/consys初期化 | NOT_TESTED | ドライバ未bind。初期化を起動していない |
| transport/data | NOT_TESTED | 読み書きしていない |
| 衛星捕捉、fix、navigation | NOT_TESTED | Debianで測位試験していない |

実機のactive DTで読み取った内容:

- `/gps@18C00000`: `mediatek,mt6990-gps`。
- `reg-names`: `conn_infra_base`, `conn_gps_base`, `conn_dyn_base`, `status_dummy_cr`, `tia2_gps_on`, `tia2_gps_rc_sel`。対応するreg tupleは6個。
- interrupts propertyは0x17c〜0x186の11エントリ。
- GPS reserved-memory nodeは`compatible=mediatek,gps-reserve-memory`、`size=0x60000`、`alignment=0x10000`、`no-map`。
- `/consys@18000000`のcompatibleは`mediatek,mt6990-consys-atf`。
- GPS/conninfra関連のロード済みmodule、driver bind、GNSS device node、dmesg初期化ログは今回の範囲で確認できなかった。

上記は実行中DTの記述とLinux列挙状態を示す。レジスタへアクセスしたこと、電源/クロックが有効であること、MCU firmwareが起動可能なことを証明しない。

## 公開OSSとの照合

参照ソースはGPL-2.0 `liudaoziwa/mainline-mt6991` commit `8e7a8e2f05ec3371bf6e498386c04b29bf03d404`。

確認できた適合点:

- `gps_dl_linux_plat_drv.c`のOF tableに`mediatek,mt6990-gps`があり、MT6990にSOC711X EMI layoutを選ぶ。
- v062 driverのMCUDL構成時IRQ数は11で、実機DTのinterruptエントリ数と数値上は一致する。
- driverが必須として名前で取得する最初の3領域 (`conn_infra_base`, `conn_gps_base`, `conn_dyn_base`) と `status_dummy_cr`、`tia2_gps_on`, `tia2_gps_rc_sel` は実機DTにある。

未解決の不一致/リスク:

1. conninfra source OF tableには`mediatek,mt6991-consys`があるが、実機の`mediatek,mt6990-consys-atf`はない。6991のplatform data/SMC/clock/power制御を6990へ流用する根拠はまだない。sourceに`CONFIG_MTK_COMBO_CHIP_CONSYS_6991`が存在しても、これはC号機MT6990対応の証拠ではない。
2. GPS driverはDTにない`tia_gps`および`tia2_gps_debug`も名前で要求する。取得失敗が許容される経路はあるが、probe後のすべての利用経路が安全か、MT6990用に無効化すべきかをまだソース追跡していない。
3. GPS platform codeにTIA/AP register writes、ATF/SMC連携、conninfra SPI、firmware loadingが含まれる。MT6990の承認済み制御ABI、ATF/firmware対応、PMIC/clock/reset初期化順との照合前にmoduleをbindすると危険である。
4. 現行P25 configには`CONFIG_MTK_GPS_SUPPORT`とMediaTek conninfra/GPS構成がない。単純なP44 `.ko`追加だけでは成立しない可能性が高い。
5. 対応するMT6990 firmware・純正daemonが公開OSSのみで代替できるかは未確定。固有firmwareや純正バイナリを公開・転用していない。

## ホスト側ビルド実験

ビルド対象はKVM成功P25と同じ公開kernel source commit `1cdda838e8475edf89b73ff0cc952005dd0b1fa7`、kernel release `6.18.63-debian-t6-proto2`。既存レシートにあるconfig SHA-256は`d5c4ac7b7f7d9da9f3fbbd62cb1e8dcf16284faa17e07877c844f76a0f1a53b8`。private kernel treeのconfig、Image、DTB、P25は変更していない。

公開OSS v062を外部モジュールとして解析ビルドし、依存を次の順に調べた。

1. connadpのbuild-in adapter群は通常`obj-y`である。依存関係調査のためだけにscratch Kbuildでmodule化し、`memcpy(dest, 0, size)`となっていたDFD handler clearを`memset`へ置換したところ、connadp.koのhost link/modpostに到達した (MODULE_DESCRIPTION警告あり)。この修正案は[patch 1](../../patches/gnss/0001-connadp-clear-dfd-handler-with-memset.patch)。本番kernel統合・実機ロードはしていない。
2. conninfraを`CONFIG_MTK_COMBO_CHIP_CONSYS_6991=y`としてhost buildし、connadpのModule.symversを与えるとconninfra.koのlink/modpostに到達した (MODULE_DESCRIPTION警告あり)。Linux 6.18 headersとの競合を避けるcompat shim差分は[patch 2](../../patches/gnss/0002-conninfra-guard-legacy-compat-shims-on-6.18.patch)。これはコンパイル可否の確認に限る。6991をMT6990に対する正しいplatform選択と認定したわけではない。
3. GPS v062/MCUDLを同一target kernel sourceに対して構築。target kernelにないGPS SMC IDをscratch preincludeから補い、Linux 6.18とのcompat shim差分を適用した。vendor codeの`missing-prototypes`, `empty-body`, `unused-value`が`-Werror`になるため、この探索ビルドでは該当警告だけ非fatal化した。
4. 上記条件のhost-only探索ビルドは、connadp.ko、conninfra.ko、gps_drv_dl_v062.koのlink/modpostまで完了した。各`.modinfo`のvermagicは`6.18.63-debian-t6-proto2 SMP mod_unload aarch64`、dependsはそれぞれ空、`connadp`、`conninfra`。ただしMT6991選択を外部変数で与え、C号機target configにないSMC IDをscratch preincludeから与え、警告を降格した探索用出力である。これは採用可能なクリーンビルド・MT6990適合・モジュールABI完全一致・実機動作のいずれも証明しない。P44へ保存もロードもしていない。

この実験から得た実装上の結論は、GPS driver単独では足りず、P25側のconninfra platform binding・secure-call定義・必要なcommon adapter exportsを含む、互換性を確認したkernel/module一式が必要ということ。仮の6991設定で生成したモジュールをC号機へ配置/ロードしてはならない。

## 安全な次工程

1. 公開または再配布可能なMT6990-specific conninfra/ATF source、DT binding、SMC contractを確認する。6991 aliasやMMIO値を推測しない。
2. 実機DTの各GPS `reg-name`とv062 driverの`gps_dl_get_iomem_by_name()`、TIA選択/利用経路を静的に全追跡し、不在named resource時の全call pathをテストする。
3. MT6990固有platform match/Kconfigを正しい証拠から追加し、Kbuildの正常な依存順 (built-in adapter exports、conninfra、GPS) と warning-free全体ビルドを行う。探索用の警告降格は製品ビルドから外し、各警告を修正または根拠付きで個別評価する。
4. P25変更が必要な場合は別の候補だけを製造し、既知good P25を保護する。署名・書込み・再起動は別承認後のゲートとする。
5. 実機bind/initはMT6990 firmware・secure firmware・power/reset依存を確認し、module probeが即座にMMIO/SMC/電源操作をするかレビューしてから、独立承認を得て実施する。
6. transport/data取得後にgpsd連携、衛星捕捉、fix、各system navigation messageを段階的に検証する。GNSS endpointの競合と位置情報の非公開を維持する。

純正B号機で確認された3D fixとGPS/GLONASS/BeiDou/Galileo navigation deliveryは比較基準のみ。Debian側の成功を意味しない。SBAS/QZSS L1Sbは別課題で、現時点UNKNOWN。
