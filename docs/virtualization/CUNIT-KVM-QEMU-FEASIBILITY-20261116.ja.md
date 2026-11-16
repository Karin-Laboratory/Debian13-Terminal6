# C号機 Debian 13 の KVM/QEMU 実現可能性

調査日: 2026-11-16  
対象: Debian 13 / `6.18.63-debian-t6-proto2` / MT6990 C号機  
実機変更: なし

## 結論

現行カーネルで `/dev/kvm` がない直接原因は、**カーネル設定で仮想化が無効**なこと。保存済みの製造証拠にある、実機リリースと一致する6.18.63カーネル設定は `CONFIG_VIRTUALIZATION` が未設定で、KVM本体も選択されていない。よって、現時点の証拠は「KVM未ビルド」を示し、「KVMモジュールの欠落」や「EL2取得失敗」を直接原因とはしない。

ARM Cortex-A55自体はEL2仮想化拡張を実装するCPUである。しかし、実際にLinuxがEL2で起動したこと、LK/ATFが非secure EL2をLinuxへ渡すことはまだ確認できていない。従って、KVM有効化後の実機利用可否は **BLOCKED / NOT_TESTED**。CPUの能力だけではboot chainのEL2引き渡しを証明しない。

## 根拠

| 証拠 | 内容 |
|---|---|
| 現行実機の所有者観測 | Debian 13、Linux `6.18.63-debian-t6-proto2`、4 CPU、`/dev/kvm`なし、KVMモジュールなし、dmesgにKVM/EL2行なし、`/proc/config.gz`あり（35,439 bytes）。このターンでは実機へ接続して再取得していない。 |
| private製造レシート | `kernel.release=6.18.63-debian-t6-proto2`、設定SHA-256 `a96a7d4f563f828df8b81a1f305c24e37443c1c63be149cf6c894772aacdb9b9`。 |
| 設定実体 | 同SHAの`embedded.config`と`kernel.config`で `# CONFIG_VIRTUALIZATION is not set`。ARM64を確認できる製造入力。 |
| 保存済みソース | 公開Linux 6.18.63ソースの`arch/arm64/kvm/Kconfig`は`VIRTUALIZATION`配下にboolの`KVM`を置く。arm64のMakefileは`CONFIG_KVM=y`時にKVM本体とhypコードを組み込む。 |
| C号機CPU | リポジトリの2026-11-14実機記録で4×Cortex-A55 r2p0。Arm Cortex-A55の公式TRMはEL2/Hyp実装を示す。 |

### 原因の分類

- `KVM_NOT_BUILT`: **PASS** — 対応する製造設定で`CONFIG_VIRTUALIZATION`が無効。
- `KVM_MODULE_MISSING`: **該当せず** — arm64 KVMはこのツリーでbool/built-in構成。未設定なら`.ko`を探しても出ない。
- `KVM_INIT_FAILED`: **未判定** — KVMを有効にしたカーネルでの初期化ログがない。
- `EL2_CPU_CAPABILITY`: **CPUコア仕様上あり** — A55 TRMに基づく。
- `EL2_BOOT_HANDOFF`: **UNKNOWN** — C号機の稼働ログにEL1/EL2判定行を保存した証拠がなく、LK/ATF遷移も未観測。

## 必要なカーネル変更

最小config fragmentは[`configs/cunit-kvm.fragment`](../../configs/cunit-kvm.fragment)の2項目。

```text
CONFIG_VIRTUALIZATION=y
CONFIG_KVM=y
```

`CONFIG_KVM=m`は不可。このLinuxツリーではKVMはbool。KVMを有効にするとKVM/arm64のコードがカーネルへ組み込まれる。実際のDebian C-unitカーネルに適用する場合は、既存のMT6990パッチ、config、Module.symvers、DTB、署名・boot-v2契約を保った新規カーネルビルドと別途認可された起動検証が必要。今回それらの実機入力・ブート成果物は変更していない。

起動後の判定は、同じ起動のdmesgで以下を確認する。

1. `CPU: All CPU(s) started at EL2` が出るか（ソース上の`arch/arm64/kernel/smp.c::hyp_mode_check()`）。
2. KVM初期化成功ログと`/dev/kvm`の出現を確認する。
3. `HYP mode not available`またはEL1ログなら、KVM configだけでは解決しない。Linux起動前のboot chainがEL2を保持・引き渡す必要がある。LK/ATF変更は今回の許可外であり、根拠・対象・復旧計画を用意した別承認が要る。

Linux arm64 KVM初期化コードはEL2/Hypが利用できない場合に初期化を拒否する。KVMをconfigへ足したことだけでKVM利用可能とは判定しない。

## QEMUとOpenWrtゲスト

OpenWrt公式`armsr/armv8`ターゲットはQEMUの`virt`機を対象とするARMv8汎用イメージを提供する。まず起動確認にはinitramfsカーネル、`-M virt`、UART consoleを使い、仮想eMMC等のデバイス固有要件を避ける。ユーザーが示した256 MiB RAM / 512 MiB diskは**初期候補値**であり、ゲストの起動・余力をまだ実測していない。

- KVM: 実機LinuxがEL2で動き、`/dev/kvm`が利用できれば`qemu-system-aarch64 -accel kvm -cpu host`で試験する。
- TCG: EL2が渡らない場合もQEMU TCGは機能上の代替候補。ただし4コアA55、約1.5 GiB availableのホストでの速度・メモリ余力は未測定。C号機のP44は過去にeMMC I/O不安定性が記録されているため、512 MiB仮想ディスクをP44上に作る性能試験はしない。RAM-backedまたは別の健全なストレージを用いる必要がある。
- OpenWrtゲストとP44のネットワークbridgeは分離して最初に起動し、管理経路へbridgeを追加しない。

一次資料: [Linux arm64 boot protocol](https://docs.kernel.org/arch/arm64/booting.html), [Linux 6.18.63 arm64 KVM Kconfig](https://github.com/torvalds/linux/blob/v6.18/arch/arm64/kvm/Kconfig), [OpenWrt armsr/armv8 releases](https://downloads.openwrt.org/releases/25.12.6/targets/armsr/armv8/), [OpenWrt QEMU guide](https://openwrt.org/docs/guide-user/virtualization/qemu), [Arm Cortex-A55 TRM](https://documentation-service.arm.com/static/649ac6d4df6cd61d528c2bf1)。

## 実施したホスト側検証

- [`scripts/check_arm64_kvm_config.py`](../../scripts/check_arm64_kvm_config.py)がARM64、`VIRTUALIZATION=y`、`KVM=y`をfail-closedで確認する。
- 合成configの正常系、仮想化未設定、KVM=m、非ARM64、未設定記法をunit testで確認する。
- 公開Linux 6.18.63ソース（保存済みsource commit `56b85307ef8b4b826c1c0172af490e2550a565cf`）の隔離コピーで`defconfig`へfragmentをmergeし、`olddefconfig`後の`ARM64=y`, `VIRTUALIZATION=y`, `KVM=y`を検証。解決済み`.config` SHA-256は`ba746ce8b4aca5d6cdbaa4feb2622150681767ba9c6fa77c5005781434b83176`。
- 同じ汎用configでarm64 KVM/EL2関連の翻訳単位86個を生成し、Kbuildの`arch/arm64/kvm/built-in.a`とnVHE/VHE archiveを作成。archive中に`kvm_init`等の定義があることを確認。一方、全ImageビルドはMTK以外の`clk-mt7987-apmixed.c:89`が現行`mtk_clk_register_plls(struct device *, ...)`へ`struct device_node *`を渡すコンパイルエラーで停止した。これは汎用defconfigが選んだ無関係なMT7987ドライバの不整合であり、KVM部分のエラーではない。対象外ドライバを無効化・修正して成功と見せることはせず、完全なImage buildはFAILと記録する。KVM archive作成は「KVMコードのコンパイル・組立て確認」に限り、最終vmlinux/ImageのリンクやMT6990対応を示さない。
- 公式OpenWrt 25.12.6 armsr/armv8 `generic-initramfs-kernel.bin`（35,754,496 bytes、SHA-256 `2b1f0796ec31201b609643beca48de20d75f2879104a20adba327cbaf64b5f2b`）をx86_64ホスト上QEMU 10.0.13 / `virt` / 256 MiB / 2 vCPU / TCGで直接起動。`/init`、procd early/ubus/init、およびconsole待受まで到達した。120秒で外部timeoutをかけて終了したため、timeoutは対話consoleを残すための試験終了であり、起動エラーではない。TCGログに`HYP mode not available`があるのはこのx86_64ホスト上のTCGゲストについてであり、C号機のEL2判定には使えない。
- C号機のKVM有効カーネル製造、P25作成、署名、実機書き込み、再起動、QEMUゲスト起動、TCG性能試験は実施していない。

## 受入マトリクス

| 項目 | 判定 | 根拠 / 次の条件 |
|---|---|---|
| 現行KVMが使えない直接原因 | PASS | 6.18.63対応設定で`CONFIG_VIRTUALIZATION`無効。 |
| CPUコアEL2能力 | PASS | Cortex-A55 TRM。 |
| 現boot chainのEL2提供 | UNKNOWN | KVM有効カーネル起動後のEL行を採取する必要。 |
| 必要なLinux設定 | PASS | VIRTUALIZATION=y、KVM=y。 |
| MT6990 KVMカーネル再ビルド | NOT_TESTED | 公開ソースはあるが、今回ターゲット構成で製造していない。 |
| 実機KVM初期化と`/dev/kvm` | NOT_TESTED | 別途カーネル起動試験が必要。 |
| OpenWrt ARM64 QEMUゲスト | NOT_TESTED | まずホストでTCG起動、次にC-unitでKVM smoke test。 |
| TCG性能・RAM余力 | NOT_TESTED | eMMCに負荷をかけない一時領域で計測。 |

## 次の最小検証

1. PR #14の最新public MT6990 source replay/configを固定し、上記fragmentを既存configへmergeして`.config`を保存する。
2. 実際のkernel release、必要な組み込みドライバ、Image/DTBの差分を確認して新規kernelをビルドする。既存署名済み成果物には触れない。
3. 実機を切り替える前に、そのP25を使った復旧条件・署名・slot fallbackを別途レビューする。
4. 認可後の単回起動でUART/dmesgのEL2行、KVM init、`/dev/kvm`を確認する。
5. KVMが成立した場合に限り、RAM 256 MiBのOpenWrt armsr/armv8 initramfsを起動し、次に一時ストレージ上で512 MiB diskを試す。失敗またはEL1なら停止し、boot chain調査へ戻る。

今回、C号機のP25/P26/P44、boot slot、bootloader、ATF、署名済みイメージは変更していない。
