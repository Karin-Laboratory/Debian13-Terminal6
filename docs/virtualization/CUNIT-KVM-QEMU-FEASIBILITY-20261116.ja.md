# C号機 Debian 13 の KVM/QEMU 実現可能性

調査日: 2026-11-16  
対象: Debian 13 / `6.18.63-debian-t6-proto2` / MT6990 C号機  
初回記録時の実機変更: なし（後続の実機検証記録を参照）

## 2026-11-16 続行記録：署名済み候補の実機起動とKVMゲスト

この節は同日後刻の最終実機検証を記録する。過去の「未試験」「実機変更なし」は当時の状態であり、以下の結果で更新する。

- ユーザー承認の範囲で、署名済みKVM候補をslot Bの純正Linux環境から`boot_a`だけへ書き込んだ。対象は32 MiBの`boot_a`で、書込み後の全量readback SHA-256は署名済み候補と一致した。P26、slot B、GPT、OEM領域は書き換えていない。P44へraw/image書込みはしていないが、後述のQEMUパッケージをAPTで導入した。候補・署名レシート・個体固有ログは非公開保管し、公開しない。
- 純正boot controlでslot Aを選択して起動。Debian復帰後に`bootslot=a`、`Linux 6.18.63-debian-t6-proto2`、`CONFIG_VIRTUALIZATION=y`、`CONFIG_KVM=y`を実測した。カーネルログは`kvm [1]: VHE mode initialized successfully`および`kvm_arm_init ... returned 0`。`/dev/kvm`は`root:kvm`のcharacter deviceとして出現した。これらはC号機LinuxがKVM用EL2を確保してKVMを初期化した肯定的な実機証拠である。
- eMMCは`/sys/kernel/debug/mmc1/ios`で要求100,000,000 Hz、実測94,999,965 Hz、HS400、8-bit、1.8 V。`cmdq_en=0`。rootは`/dev/mmcblk1p44`のext4 `rw,noatime`で正常マウント。QEMU試験後に採取したカーネルログにはMMC timeout/error、ext4 I/O errorの新規記録なし。温度sysfsの読み取り値は試験後約57–65°Cの範囲だった（複数センサーの生値であり、特定センサーをCPU温度とは解釈しない）。
- C号機へDebianの`qemu-system-arm`パッケージを追加。APTは新規31パッケージ、0 upgrade、0 removal。QEMU 10.0.13を使用し、`qemu-system-aarch64 -accel kvm -machine virt -cpu host -m 256 -smp 1`で、公式OpenWrt 25.12.6 `armsr/armv8/generic-initramfs-kernel.bin`（SHA-256 `2b1f0796ec31201b609643beca48de20d75f2879104a20adba327cbaf64b5f2b`）を起動した。ゲストはLinux 6.12.112 / aarch64、`/init`、procd early/ubus/initを通過して対話コンソールに到達した。
- 稼働中にホスト側QEMU PIDの`/proc/<pid>/fd`から`/dev/kvm`が開かれていることを直接確認した。ゲストのvirtio-net `eth0`は`br-lan`へ接続されUP。試験中だけゲストのアドレスを`10.0.2.15/24`へ設定し、QEMU user-mode networkingの仮想gateway `10.0.2.2`へping 3/3成功（損失0%）。このuser-modeネットワークは家庭内LAN/管理LANへbridgeしていない。ゲストには仮想ディスクを付けず、ゲストの書込みはRAM initramfs内に限定した。
- ゲストを終了し、QEMUプロセス停止、Debian SSH・管理Ethernetが維持されていることを確認。UARTロガーは起動ログをraspi4上の非公開ディレクトリへ保存した。C号機上のOpenWrt kernel imageは`/run`に置いたRAM上の一時ファイルで、検証後に削除した。P44上のネットワークや起動設定は変更していない（QEMUパッケージ導入による通常のAPT書込みを除く）。
- boot controlはAをtrialのまま保持した（A success=0、B success=1）。試験後にmiscを変更してAを恒久成功扱いにする操作はしていない。slot Bの成功フラグと復旧可能性を維持した。候補の通常再起動後の自動選択・再現性は未試験であり、追加再起動もしていない。

### この検証の判定

| 項目 | 判定 | 実測 |
|---|---|---|
| KVM対応Linux全体のビルド | PASS（private source制約あり） | Imageと105 modulesを生成、release一致 |
| 署名済み候補の`boot_a`書込み/readback | PASS | 対象限定、全量readback一致。生SHA/署名レシートはprivate |
| EL2/KVM初期化 | PASS | VHE initialized、`kvm_arm_init`戻り値0 |
| `/dev/kvm` | PASS | device出現、QEMU稼働中にQEMUがopenしているFDを確認 |
| ARM64 OpenWrtゲスト | PASS | OpenWrt 25.12.6、Linux 6.12.112、procd console |
| 仮想ネットワーク | PASS | virtio-net、仮想gateway ping 3/3 |
| C号機ホストの再起動後復帰 | NOT_TESTED | KVM候補boot後の追加再起動は未実施 |
| A trialの恒久成功化 | NOT_PERFORMED | B success=1維持、A success=0 |

したがってC号機の判定は**「実機KVM動作確認済み」**。公開PR #14の入力だけからprivate C-unit kernel buildを再現できること、および候補の再起動後自動復帰は別途未達。

## 2026-11-16 続行記録：C-unit向けホストビルド

この節は実機署名・起動試験前に作成したホストビルド時点の履歴である。直前の実機検証節が最終状態であり、以下の当時のNOT_TESTED記載は後続試験で解消した。

- PR #14の最新確認HEADは `e05811f8d4d3ee2606f44f27218ef59132a39a5f`。公開kernel/network/experimental-DTB/P44-rootfs再現CIはPASS。公開kernel archiveのSHA-256は `c0127d88bdf6cb7a6ff9c81563f17dc059ace870c0e1a10e87dee5a1904158f8`（Linux 6.18.63、source commit `1cdda838e8475edf89b73ff0cc952005dd0b1fa7`）。この公開再現成果はMT6990向け全C-unit本番ソース一式ではない。
- C-unit用のKVM有効全kernel buildは、既存の非公開C-unitソースツリーを複製した隔離コピー上で完了した。元ツリーは変更していない。releaseは `6.18.63-debian-t6-proto2`、`Image`と105 modulesを生成し、所要時間は約26分19秒。設定は一致するproto2製造config（SHA-256 `a96a7d4f563f828df8b81a1f305c24e37443c1c63be149cf6c894772aacdb9b9`）から `configs/cunit-kvm.fragment` を適用し、`CONFIG_VIRTUALIZATION=y`, `CONFIG_KVM=y` を確認した。解決後config SHA-256は `d5c4ac7b7f7d9da9f3fbbd62cb1e8dcf16284faa17e07877c844f76a0f1a53b8`。
- 成果物: Image SHA-256 `dd077159730686875a5dbffe3853bff5e23043cb22087546192cb42321d31ce1`（18,790,408 bytes）、vmlinux `05cdc5753a24cf04ca64b3aae0772be3b4b6c49d86c006f88d92499205c73e5a`、System.map `c56e7603496592503093779585d1639d0b5885d7d64678440d2eaffbea95328c`。vmlinuxに `kvm_init` と `__kvm_nvhe___kvm_hyp_init` を確認。これはホスト上の完全なkernel build PASSであり、実機起動PASSではない。private tree由来のため、PR #14の公開入力だけからの再現性は未達。
- 起動候補用DTBはno-CQE候補から分離生成し、`/mmc@11230000/max-frequency`を100MHzへ変更、`supports-cqe`なしを維持した。意味差分はこのプロパティ1点のみ。DTB SHA-256 `a6bef90e18c0a16934e6c4196fea60408a1fed08b6ef9b62c7fbe5d7c5632d91`。署名済みPR #3 DTBとのbyte-for-byte比較は未実施。
- kernel Image、上記DTB、private P44 initramfsから32MiBのtemplate-free unsigned P25候補を生成し、独立構造/readback verifierはPASS。LK受理・boot試験は未実施で、未署名。P25とP44 initramfsは非公開保管し、SHAや内容をこの公開文書に記録しない。
- このKVM候補をC号機へ署名・書込み・起動していない。従ってEL2、KVM初期化、`/dev/kvm`、C-unit上のQEMU/OpenWrt KVMゲストはすべてNOT_TESTEDのまま。既存のx86_64ホスト上OpenWrt TCG起動結果はC-unitのKVM証拠ではない。
- 実機ゲートの現状: AGENTS.mdで許可された経路はraspi2 gatewayのみ。raspi2の非特権codexからC-unit用SSH秘密鍵/agent keyが利用できず、serial deviceも見つからなかった。従って実機の現在状態をこのセッションから取得できず、起動操作はしていない。安全な実機試験には許可されたC-unit管理資格情報またはUART経路の復旧が必要。また実機操作前にこの候補の正確なSHAに対する署名および一回起動の承認が必要。

## 初回調査時点の結論（後続の実機検証で更新済み）

当時の現行カーネルで `/dev/kvm` がなかった直接原因は、**カーネル設定で仮想化が無効**だったこと。保存済み製造証拠の6.18.63設定は `CONFIG_VIRTUALIZATION` 未設定、KVM本体も未選択だった。これはKVM候補起動前のベースラインである。

当時はEL2引き渡しが未確認だった。後続のKVM候補起動ではLinuxログにVHE初期化成功と`kvm_arm_init`戻り値0が記録され、C号機で利用可能なEL2が確認された。現在の最終判定は本書冒頭の「実機KVM動作確認済み」である。

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

## 初回調査時点の受入マトリクス（後続結果で更新済み）

| 項目 | 判定 | 根拠 / 次の条件 |
|---|---|---|
| 現行KVMが使えない直接原因 | PASS | 6.18.63対応設定で`CONFIG_VIRTUALIZATION`無効。 |
| CPUコアEL2能力 | PASS | Cortex-A55 TRM。 |
| 現boot chainのEL2提供 | UNKNOWN | KVM有効カーネル起動後のEL行を採取する必要。 |
| 必要なLinux設定 | PASS | VIRTUALIZATION=y、KVM=y。 |
| MT6990/C-unit KVMカーネル全体のホストビルド | PASS_WITH_PRIVATE_SOURCE_LIMITATION | C-unit向けprivate treeの隔離コピーからImage/modules全体を生成。公開PR #14の入力のみで同一buildを再現する工程は未整備。 |
| 実機KVM初期化と`/dev/kvm` | PASS | 後続の署名済み候補起動でVHE初期化、`/dev/kvm`、QEMU FDを確認。 |
| OpenWrt ARM64 QEMUゲスト | PASS | 後続のC-unit KVMでLinux/procd consoleとuser-mode仮想gateway疎通を確認。 |
| TCG性能・RAM余力 | NOT_TESTED | 今回はKVMを使用。C-unit TCG性能は未測定。 |

## 初回調査時点での次の検証案（完了済み項目を除く）

1. PR #14の公開再現をC-unit完全ソースへ拡張するか、private source provenanceをレビュー可能な形で固定し、KVM対応kernel buildを第三者再現可能にする。
2. KVM候補の追加再起動試験は別の安全サイクルで行い、slot B成功フラグと復旧手順を維持する。
3. A trialを恒久成功へ変更する必要がある場合は、そのboot-control更新と復旧条件を別途確認する。現在はA success=0、B success=1のまま。

後続の実機試験では署名済み候補を`boot_a`へ書き込み、全量readback後にslot Aから起動した。P26、P44、slot B、GPT、OEM領域、bootloader、ATFは変更していない。QEMU導入パッケージによる通常のAPT書込みを除き、P44の永続設定は変更していない。
