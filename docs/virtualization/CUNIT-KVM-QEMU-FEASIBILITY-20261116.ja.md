# C号機 Debian 13 の KVM/QEMU 実現可能性

調査日: 2026-11-16  
対象: Debian 13 / `6.18.63-debian-t6-proto2` / MT6990 C号機  
実機変更: なし

## 2026-11-16 続行記録：C-unit向けホストビルド

この節は上記の初期調査を更新する。以降の記述を最新状態として扱う。

- PR #14の最新確認HEADは `e05811f8d4d3ee2606f44f27218ef59132a39a5f`。公開kernel/network/experimental-DTB/P44-rootfs再現CIはPASS。公開kernel archiveのSHA-256は `c0127d88bdf6cb7a6ff9c81563f17dc059ace870c0e1a10e87dee5a1904158f8`（Linux 6.18.63、source commit `1cdda838e8475edf89b73ff0cc952005dd0b1fa7`）。この公開再現成果はMT6990向け全C-unit本番ソース一式ではない。
- C-unit用のKVM有効全kernel buildは、既存の非公開C-unitソースツリーを複製した隔離コピー上で完了した。元ツリーは変更していない。releaseは `6.18.63-debian-t6-proto2`、`Image`と105 modulesを生成し、所要時間は約26分19秒。設定は一致するproto2製造config（SHA-256 `a96a7d4f563f828df8b81a1f305c24e37443c1c63be149cf6c894772aacdb9b9`）から `configs/cunit-kvm.fragment` を適用し、`CONFIG_VIRTUALIZATION=y`, `CONFIG_KVM=y` を確認した。解決後config SHA-256は `d5c4ac7b7f7d9da9f3fbbd62cb1e8dcf16284faa17e07877c844f76a0f1a53b8`。
- 成果物: Image SHA-256 `dd077159730686875a5dbffe3853bff5e23043cb22087546192cb42321d31ce1`（18,790,408 bytes）、vmlinux `05cdc5753a24cf04ca64b3aae0772be3b4b6c49d86c006f88d92499205c73e5a`、System.map `c56e7603496592503093779585d1639d0b5885d7d64678440d2eaffbea95328c`。vmlinuxに `kvm_init` と `__kvm_nvhe___kvm_hyp_init` を確認。これはホスト上の完全なkernel build PASSであり、実機起動PASSではない。private tree由来のため、PR #14の公開入力だけからの再現性は未達。
- 起動候補用DTBはno-CQE候補から分離生成し、`/mmc@11230000/max-frequency`を100MHzへ変更、`supports-cqe`なしを維持した。意味差分はこのプロパティ1点のみ。DTB SHA-256 `a6bef90e18c0a16934e6c4196fea60408a1fed08b6ef9b62c7fbe5d7c5632d91`。署名済みPR #3 DTBとのbyte-for-byte比較は未実施。
- kernel Image、上記DTB、private P44 initramfsから32MiBのtemplate-free unsigned P25候補を生成し、独立構造/readback verifierはPASS。LK受理・boot試験は未実施で、未署名。P25とP44 initramfsは非公開保管し、SHAや内容をこの公開文書に記録しない。
- このKVM候補をC号機へ署名・書込み・起動していない。従ってEL2、KVM初期化、`/dev/kvm`、C-unit上のQEMU/OpenWrt KVMゲストはすべてNOT_TESTEDのまま。既存のx86_64ホスト上OpenWrt TCG起動結果はC-unitのKVM証拠ではない。
- 実機ゲートの現状: AGENTS.mdで許可された経路はraspi2 gatewayのみ。raspi2の非特権codexからC-unit用SSH秘密鍵/agent keyが利用できず、serial deviceも見つからなかった。従って実機の現在状態をこのセッションから取得できず、起動操作はしていない。安全な実機試験には許可されたC-unit管理資格情報またはUART経路の復旧が必要。また実機操作前にこの候補の正確なSHAに対する署名および一回起動の承認が必要。

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
| MT6990/C-unit KVMカーネル全体のホストビルド | PASS_WITH_PRIVATE_SOURCE_LIMITATION | C-unit向けprivate treeの隔離コピーからImage/modules全体を生成。公開PR #14の入力のみで同一buildを再現する工程は未整備。 |
| 実機KVM初期化と`/dev/kvm` | NOT_TESTED | 別途カーネル起動試験が必要。 |
| OpenWrt ARM64 QEMUゲスト | TCG_HOST_ONLY | x86_64 hostのTCGでprocd consoleまで起動済み。C-unit上KVM guestはNOT_TESTED。 |
| TCG性能・RAM余力 | NOT_TESTED | eMMCに負荷をかけない一時領域で計測。 |

## 次の最小検証

1. PR #14の公開再現をC-unit完全ソースへ拡張するか、private source provenanceをレビュー可能な形で固定し、buildを第三者再現可能にする。
2. 現在利用可能な実機管理鍵/UART経路を確保する。raspi2 gatewayの境界を越える回避は行わない。
3. 別途承認後、署名・LK適合性・対象P25 SHA・slot B復旧を確認して単回起動し、UART/dmesgのEL2行、KVM init、`/dev/kvm`を観測する。
4. KVMが成立した場合に限り、RAM 256 MiBのOpenWrt armsr/armv8 initramfsを独立ネットワークで起動し、procdとゲスト内Linuxを確認する。

今回、C号機のP25/P26/P44、boot slot、bootloader、ATF、署名済みイメージは変更していない。
