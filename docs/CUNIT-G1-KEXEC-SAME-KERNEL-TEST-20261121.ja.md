# C号機 G1: 既存署名済みP25から同一ARM64 Imageを取り出し、kexec_loadを実証する（2026-11-21）

> **今回の対象はG1の前半。** 現在実行中のDebian `6.18.63-debian-t6-proto2` が持つ `CONFIG_KEXEC=y` を利用する。P25/P26/GPT/misc/slot Bへの書込みや実機再起動を**このスクリプトは行わない**。G1の実際の第2段起動は、別途UART監視と手動操作が必須。

## 現時点のC号機実測（所有者の端末出力）

- `uname -r`: `6.18.63-debian-t6-proto2`、`bootslot=a`、実際のrootfsは `/dev/mmcblk1p44` (ext4)。
- `CONFIG_KEXEC=y`, `CONFIG_KEXEC_CORE=y`, `# CONFIG_KEXEC_FILE is not set`, `/proc/sys/kernel/kexec_load_disabled=0`。したがって利用候補は `kexec_load` (legacy syscall)。
- `/sys/firmware/fdt` は 177,338 bytes。`kexec-tools`は未インストール、`/boot`および`/lib/modules/.../`から生のARM64 `Image`は発見できなかった。
- P25 `/dev/mmcblk1p25`=32MiB、P26 `/dev/mmcblk1p26`=128MiB SquashFS（マウントなし）、P43=453MiB ext4、P44=2.5GiB ext4（使用中）。
- `lan2@eth1` は `192.168.3.1/24`、TCP/22でOpenSSH待受。`/dev/watchdog`は存在（自動復旧は仕様外）。
- C号機のシステム時計は `2026-11-17` を指している。パッケージ導入の前に時刻同期の正常性を確認する。
- PR #41が記載する**署名済み起動実績P25**の全長32MiB SHA-256: `74c1c98b31cdba54f71d16f1983fbeff347bb334c5ae7d7f1353cd57f734936e`。**端末P25がこの値と一致する保証はまだない**。スクリプトが全量照合し、異なれば停止する。

## 実行順序

```sh
# 既存Debianのroot shell。作業ブランチのスクリプトを取得して実行。
git clone --branch codex/cunit-g1-kexec-ram-stage-20261121 --single-branch \
  https://github.com/Karin-Laboratory/Debian13-Terminal6.git /root/cunit-g1
cd /root/cunit-g1

# A. 何も変更しない環境確認
python3 scripts/cunit-kexec-g1.py inspect

# B. P25を読み取り、既知のSHAと全量一致した場合のみ
#    Android boot v2からARM64 Imageを復元。/runのRAMへ保存。
python3 scripts/cunit-kexec-g1.py stage

# ここで署名済みP25のSHAとImageサイズ/ハッシュを控える。
# boot_a、P26、GPT、miscを変更せず、/run以外の新規データは作らない。
```

> 初回に`git`がなければ、外部PCからスクリプト単体を転送する。スクリプトは標準Python3ライブラリのみを使う。`/dev/disk/by-partlabel/boot_a`がなければ`--p25=/dev/mmcblk1p25`を明示するが、**必ずPARTLABELで対象を再照合**する。

```sh
# C. 時刻とパッケージ取得環境を診断（時刻が4日ずれている点に注意）
date -u
timedatectl status || true
ip route
# 時刻同期と通信を確立してから、必要なら:
apt-get update
DEBIAN_FRONTEND=noninteractive apt-get install -y kexec-tools

# D. オーナーがUART/復旧導線を確認後、RAMへカーネルをロード。
#    実行しても第2段カーネルへは飛ばない。
python3 scripts/cunit-kexec-g1.py load

# E. ロード状態を消したい場合
python3 scripts/cunit-kexec-g1.py unload
```

**重要**：パッケージ導入によって`kexec`が通常のシステム再起動に使用される設定になっていないことも確認する。今回のスクリプトには`-e`、`--exec`、再起動、`dd`、`mkfs`、`sgdisk`、`reboot`の処理を入れていない。`--load`が成功しても**G1は部分PASS**であり、第2段の起動実証ではない。

## なぜこの方法か

既存の公開製造コードのAndroid boot-v2作成経路は、ARM64 `Image` をgzip圧縮してP25へ収録する。対応する開発版ではinitramfsをカーネルへ組み込む設計になっている。したがって本スクリプトは署名済みP25のSHAを厳格照合した後、Android boot v2ヘッダー、gzip、ARM64 magicを検査して`Image`を抽出する。**稼働中の実機P25が同じ形式であることは未確認**のため、形式が異なるときには原因を調査して停止する。

`kexec --kexec-syscall --load ... --dtb=... --append=...` を選ぶのは、現在のカーネルで`CONFIG_KEXEC_FILE`が無効だから。DTBには現在稼働中の`/sys/firmware/fdt`をコピーして使用する。bootargsは現行`/proc/cmdline`を使用するが、`root=/dev/mmcblk0p26`が現在のP44と一致しないのは**既存initramfsの引継ぎ処理**によるものと見られる。第2段でも同じ引継ぎが動くかが実機検証対象。

## 実際の`kexec`ジャンプ前に必要な条件

1. P25の実物全量SHA一致、G1ツールの`stage`がPASS、`load`がPASS。
2. P25・P44の復元可能なバックアップと、slot Bの手動起動方法・UARTログ収集経路が使用可能であること。
3. kernel/DTB/initramfsの由来と互換性を確認。`kexec`の第2段はLKの初期化を飛ばすため、eMMC、GIC、clock/reset、予約メモリ、LANの再初期化に失敗し得る。
4. `kexec -e`は**UART監視付きの別工程**として行い、実際のLinux起動・P44のマウント・SSH復帰でG1完了と判定する。ユーザー操作による明示的な第2段起動と復旧措置が必要。

## 次のゲート

- **G2**: 現在P26がマウントされていないことは確認済み。ただしLKが起動時にP26の形式やハッシュを参照するかは未実証。G1完了後、原本保存のうえP26 ext4化を試す。**現時点ではP26を書き換えない。**
- **G3**: `misc` P1のブート制御方式が不明。所有者は試験進行を許可したが、実際の構造を調べる前に推測のバイト列を書かない。G1とは別にread-only解析を先行する。
- **G4**: Watchdog自動復旧は不採用。失敗したらUART／手動再起動／純正Bから戻す。slot Bが存在することと実際に復旧できることを混同しない。

## オフライン単体試験

```sh
python3 -m unittest discover -s tests -p test_cunit_kexec_g1.py -v
python3 -m py_compile scripts/cunit-kexec-g1.py
```

> このブランチは検証用の実装PRであり、2026-11-21確定の共通P25/P26/P43仕様をmainへ反映済みと称しない。既存Debian憲章v1.4との衝突は別の設計変更PRとして扱う。

## 追記：所有者によるC号機RAM stage実機試験（2026-11-21）

**結果：`inspect=PASS`、`stage=PASS`。これらは所有者がC号機のシェルから貼り付けた実測ログに基づく。GitHubのホスト上で実機試験したことにはしない。**

- 転送済みスクリプト `/root/cunit-kexec-g1.py` SHA256：`e26361d92368b6fb0e963962d41d5bc79fb601f18903b22e46b66c39dc634573`
- `inspect`: `HOST_PASS kernel=6.18.63-debian-t6-proto2 FDT_bytes=177338`
- 実機P25 `/dev/mmcblk1p25` SHA256：`74c1c98b31cdba54f71d16f1983fbeff347bb334c5ae7d7f1353cd57f734936e`。PR #41の起動実績版と**一致**。
- P25内のgzip ARM64 Image展開：**18,921,480 bytes**、SHA256 `141b6750698cb362169cc150974b3464577d6ab5fa98aa941449fc3990c8ad00`。
- 実機FDT：**177,338 bytes**、SHA256 `814a6cdba3d8c9aa8a2ce787a48aece35cddb94475deb4a466d36f90fddaa14a`。
- `stage`結果：`STAGE_PASS: RAM only; no kexec syscall, no reboot`、結果保存場所 `/run/terminal6-kexec-g1/`。
- 現在のC号機には`git`がなく、隔離LANで外向きネットワークアクセスなし。スクリプトはraspi4で取得し、既存の厳格なSSHホスト鍵検証を使ってC号機へ転送した。

### 次の安全な操作

`kexec-tools`はDebian trixie arm64の公式パッケージを**raspi4で取得し、C号機へscp転送**。C号機では`dpkg-deb -x`で`/root/g1-kexec-bin/`へ**展開のみ**行う（`dpkg -i`や`apt install`によるsystemd/reboot hook変更を避ける）。`ldd`と`kexec --version`を確認後、既存スクリプトの`load`でRAMロード試験。`kexec -e`は別工程。ロード成功の時点でも第2段起動は未確認。

参考：Debian trixie arm64 `kexec-tools` パッケージは `1:2.0.29-2+b1`、`/usr/sbin/kexec` を収録（https://packages.debian.org/trixie/arm64/kexec-tools/filelist）。ダウンロードはDebian公式ミラーから行う。

**ゲート判定（この追記時点）：** G1 P25全量照合 PASS / Image抽出 PASS / RAM `kexec_load` NOT_TESTED / 第2段Linux起動 NOT_TESTED。G2/G3/G4は未実施。

## 追記：kexec-toolsの実機実行依存不足（2026-11-21）

所有者がDebian trixie arm64 `kexec-tools` を `dpkg-deb -x` で /root/g1-kexec-bin/ に展開。実際の `ldd` と `--version` で以下を観測：

```text
libxenctrl.so.4.20 => not found
kexec: error while loading shared libraries: libxenctrl.so.4.20
BLOCKED: ... returned non-zero exit status 127
```

**判定：G1 RAM kexec_load は未到達（BLOCKED_BY_USERSPACE_DEPENDENCY）。カーネル拒否・DTB不適合・kexec失敗の証拠ではない。** `file` コマンド未導入も確認したが重要ではない。

公式Debian trixie arm64の `libxenmisc4.20` に `/usr/lib/aarch64-linux-gnu/libxenctrl.so.4.20` が含まれる（[Debianファイル一覧](https://packages.debian.org/trixie/arm64/libxenmisc4.20/filelist)）。2026-11-21の公式パッケージは `4.20.4+63-g7abfd2bce2-0+deb13u1`（[ダウンロード](https://packages.debian.org/trixie/arm64/libxenmisc4.20/download)）。SHA256 `0210f704762f70408420191458ee6814f284ca911b1df451bd1dbfffcae10390`。SSH/raspi4経由でパッケージを転送、**別ディレクトリへ展開してLD_LIBRARY_PATHでローカル検証**。このパッケージにはXen関連の依存ライブラリがさらに複数あるため、必ず `ldd` で次の不足を確認してから`load`を再試行する。Xen hypervisor自体をインストールする必要はない。

検証作業によって `P25`、`P26`、`GPT`、`misc` を書き換えない。後段実行`kexec -e`を行わない。

## 追記：Xen動的リンクの追加6ライブラリ（実機ログ）

所有者が`libxenmisc4.20_4.20.4+63-g7abfd2bce2-0+deb13u1_arm64.deb`をDebian公式ミラーから取得、SHA256 `0210f704762f70408420191458ee6814f284ca911b1df451bd1dbfffcae10390`照合PASS、C号機へSSH転送。`dpkg-deb -x`で別領域へ展開して`LD_LIBRARY_PATH`を指定した。

その結果、`libxenctrl.so.4.20`本体は解決したが、`ldd`で次の**6個**が未解決：
`libxentoollog.so.1`, `libxencall.so.1`, `libxenevtchn.so.1`, `libxengnttab.so.1`, `libxenforeignmemory.so.1`, `libxendevicemodel.so.1`。

`kexec --version`は`libxentoollog.so.1`ロードエラーで失敗。**G1は依然BLOCKED（ランタイム依存不足）、`kexec_load` syscalls未実施。** 次回はDebian security repoの同バージョンで `libxentoollog1`, `libxencall1`, `libxenevtchn1`, `libxengnttab1`, `libxenforeignmemory1`, `libxendevicemodel1` と間接依存 `libxentoolcore1`, `libxenhypfs1`, `libxenstore4` を同時に取得して隔離領域へ展開。再度 `ldd` と `--version` を検証し、未解決ならそこでSTOP。その他の装置書込み・`kexec -e`なし。

## 追記：Xen依存ライブラリ解決とkexec-tools起動PASS（2026-11-21）

所有者がraspi4から9種のDebian arm64/Xen補助パッケージを隔離LANのC号機に転送し、`sha256sum -c SHA256SUMS`ですべてPASSを確認。各パッケージを`dpkg-deb -x`で`/root/g1-kexec-lib`へ展開し、`LD_LIBRARY_PATH=/root/g1-kexec-lib/usr/lib/aarch64-linux-gnu`として動的リンクを解決。

実機出力：

```text
./libxencall1.deb: OK
./libxendevicemodel1.deb: OK
./libxenevtchn1.deb: OK
./libxenforeignmemory1.deb: OK
./libxengnttab1.deb: OK
./libxenhypfs1.deb: OK
./libxenstore4.deb: OK
./libxentoolcore1.deb: OK
./libxentoollog1.deb: OK
ALL LIBRARIES RESOLVED
kexec-tools 2.0.29
```

**判定：G1ユーザー空間実行ファイル準備PASS、`kexec_load`未実行、`kexec -e`未実行。** `tar`の未来タイムスタンプ警告はC号機の時計が約4日遅れている影響で、パッケージSHA検証・展開は正常に完了した。

次は同一シェルで`export LD_LIBRARY_PATH=/root/g1-kexec-lib/usr/lib/aarch64-linux-gnu`、`export PATH=/root/g1-kexec-bin/usr/sbin:$PATH`を設定し、`python3 /root/cunit-kexec-g1.py load`を実行。結果に応じてロード方法やドライバ再初期化の検証を切り分ける。ロードしても自動的には起動しない。

## 追記：C号機 kexec RAMロード正常終了（2026-11-21）

所有者のC号機シェルの実機ログで次の結果を観測：

```text
LOADING_INTO_RAM_ONLY; this will NOT transfer control
Can't open (/proc/kcore).
Can't get the symbol of _text to calculate page_offset.
KEXEC_LOAD_PASS: loaded but second-stage boot NOT tested; use UART for separately approved kexec -e
LOAD_EXIT_CODE=0
```

`kexec --kexec-syscall --load` は終了コード0で完了したため**G1 RAMロード試験PASS（ツール終了コード）**。ソース上の`/proc/kcore` / `_text`情報解析警告は非致命扱いで残っており、次に`/sys/kernel/kexec/loaded`（互換パス`/sys/kernel/kexec_loaded`）が`1`であることを独立確認する。該当表示の独立確認ができるまでは、異常なくロードされたことの別証拠にはしない。

第2段カーネルへの制御移行（`kexec -e`）・Linux起動・P44のマウント・SSH復帰はいずれも**NOT_TESTED**。再起動せず装置への永続書込みも無し。独立復旧導線（raspi4 UART、純正slot B）を確認してから、所有者操作で有限回の`kexec -e`試験に進む。

## 追記：カーネル自身のkexecロード確認PASS（2026-11-21）

所有者がC号機で`/sys/kernel/kexec_loaded`を読み取ったところ、**`1`** を実測。

```text
/sys/kernel/kexec_loaded = 1
```

先行する`kexec --load`終了コード0に加え、**実カーネル側のload状態表示もPASS**。第2段へのジャンプ、Linux起動、eMMC再認識、P44 rootfs、SSH復帰は**いずれも未検証**。ロードされた第2段イメージはRAM上にあり、実機は現時点で稼働中。次段の`kexec -e`はユーザーがraspi4のUART監視、事前のP44書込み同期、バックアップ・手動復旧手順を準備した後で行うこと。ブート制御フラグ・P26・P25には触れない。

## 追記：第2段ジャンプ後のネットワークとSSH鍵変化（2026-11-21、所有者実機観測）

所有者が`/root/g1-kexec-bin/usr/sbin/kexec -e`を実行した直後、raspi4からC号機`192.168.3.1`への初回SSHは`No route to host`。しかしその後の同一raspi4での確認では、`eth0`から`192.168.3.1`へ**ping 3/3成功**（平均約0.648ms）し、Neighbor MAC `18:2c:a9:03:1a:78` を観測。**kexec前Debianのlan2 MACは `c2:4c:3f:f3:9b:a9`**。

SSH TCP/22応答は得られるが、既知のホスト鍵と一致しない：

```text
WARNING: REMOTE HOST IDENTIFICATION HAS CHANGED!
ED25519 fingerprint SHA256:5nDaTMqEuIOQNrOAayFxSpHnpcAI904Fx4cYUycBDeg
Offending ECDSA key in /home/masataka/.ssh/known_hosts:4
```

ユーザーは`ssh-keygen -R 192.168.3.1`を実行済みで、以前のknown_hostsは`known_hosts.old`に退避されている。以後は`StrictHostKeyChecking=yes`によって新規鍵の受理が拒否されている。**新ホスト鍵はSSHサービスが違うか、初期化でホスト鍵を再生成した可能性を示すが、これだけでは第2段Debian実起動成功を示さない。** UART監視はraspi4 `/dev/ttyUSB0`を`cat` PID 21540が保持し、`~/cunit-g1/g1-kexec-uart.log`は空。監視開始前のブートログは残っていない可能性がある。

次の調査：`ssh-keyscan`でED25519指紋を観測し`known_hosts.old`と比較。物理直結を確認し、独立の`UserKnownHostsFile`を使い`StrictHostKeyChecking=ask`で明示同意の後、ログインできる場合は`uname -a`、`/proc/cmdline`、`findmnt /`、`/etc/os-release`、uptime、ネットワークMACで後段Debianか別OSかを識別する。**現時点でG1第2段Linux起動はUNKNOWNでありPASSと報告しない。**

## 追記：kexec -e後、slot B純正起動を実測（2026-11-21）

所有者が第2段カーネルをRAMロードし、`/sys/kernel/kexec_loaded = 1`を確認後、C号機で`/root/g1-kexec-bin/usr/sbin/kexec -e`を実行。直後はSSHに接続できなくなったが、raspi4から`ping -I 192.168.3.71 -c 3 192.168.3.1`が3/3で応答した。SSH接続先のED25519指紋は`SHA256:5nDaTMqEuIOQNrOAayFxSpHnpcAI904Fx4cYUycBDeg`に変化し、所有者は指紋を確認して新しい専用known_hostsへ登録した。

接続先はDebianではなく**純正slot BのBusyBox 1.33.2、プロンプト `root@SBA6D:~#`**であった（所有者による実機確認）。`Warning! There is no root password defined on this device!` と表示された。**G4純正slot BのSSH復帰実証PASS**。ただし初期無認証SSHなのでLAN物理隔離を維持。

**G1最終判定：第2段起動 NOT_PROVEN / 実機結果は純正Bへの復帰。** RAMロードのPASSを後段Linuxの起動PASSと混同しない。故障経路は現時点で不明：kexec実行処理の問題、転送直後のリセット、2段目MMC/割込み/DTB/clock/メモリの初期化失敗、LKのslot Aのretry/success状態など可能性が残る。`kexec -e`自体の戻り値はSSH切断で確認できない。

既存UART `cat /dev/ttyUSB0` PID 21540に対応する`~/cunit-g1/g1-kexec-uart.log`は所有者確認時点で空であり、起動前からのログが得られていない可能性がある。次回は**実行前から独立したUART監視**を確認し、実機変更なしの純正B read-only調査（`/proc/cmdline`、`dmesg`、`/sys/fs/pstore`の有無、起動制御APIの読取り）を先行。**現時点ではboot control、P25/P26、slot A/B、P44を変更しない。**

次回実機実験の重要点：`kexec`前の現行cmdline `init=/etc/preinit root=/dev/mmcblk0p26` と、実際のP44 rootfs `/dev/mmcblk1p44` が異なる。現行内蔵initramfsが`rootfs_data`を識別して後段へ移行できるか、残存デバイス初期化の影響に注意。ブート時pstore/ramoopsが取得できるなら原因を切り分ける。

## 追記：純正slot BのpstoreからDebian panicを発見（2026-11-21）

所有者が純正B `root@SBA6D` の`/sys/fs/pstore/`を読取り、`console-ramoops-0`（3857 bytes）、`dmesg-ramoops-0`（6753 bytes）、`dmesg-ramoops-1`（6794 bytes）に次の**Linux 6.18.63-debian-t6-proto2**の例外・panicを観測した。private原本自体を公開repoへ転記せず、障害分析に必要な抜粋のみ記録する。

```text
[    6.358779] Internal error: synchronous external abort: 0000000096000010 [#1] SMP
[    6.383694] CPU: 3 UID: 0 PID: 1748 Comm: (udev-worker) ... 6.18.63-debian-t6-proto2 #2
[    6.418100] pc : mt76_mmio_rmw+0xc/0x40 [mt76]
[    6.422598] lr : mt7996_reg_map_l1+0x5c/0xa0 [mt7996e]
[    6.517081] mt76_mmio_rmw+0xc/0x40 [mt76]
[    6.521568] __mt7996_reg_remap_addr+0x120/0x1a0 [mt7996e]
[    6.531451] mt7996_mmio_probe+0xf4/0x198 [mt7996e]
[    6.536385] mt7996_pci_probe+0xd8/0x5e0 [mt7996e]
[    6.727158] Kernel panic - not syncing: synchronous external abort: Fatal exception in interrupt
[    6.823178] Rebooting in 1 seconds..
```

**診断**：Debian 6.18.63カーネルの起動後約6.36秒でudevがPCIe Wi-Fiドライバ`mt7996e`をロードし、`mt76`のMMIOレジスタ読取り中にsynchronous external abortを起こしたことが確定。このpanicと再起動は、kexec試験後に純正Bが起動した時系列に**整合**するが、pstoreの時刻はC号機の誤ったシステム時計の影響があり、今回のkexecと**一対一対応することは未証明**。第2段起動成功は現段階では「強い状況証拠」であり、G1 full boot PASSとしない。`pstore: backend (ramoops) writing error (-28)` は後段のpstore保存容量不足であり、panicの本体原因ではない。

**次の仮説検証（実機実行は別途安全管理のもと）**：起動時のコマンドラインに `module_blacklist=mt7996e modprobe.blacklist=mt7996e` を一時的に付加し、kernel module loadとユーザー空間の自動probeをともに抑制する（Linuxカーネルの `module_blacklist` はloadable modulesの禁止、`modprobe.blacklist` はmodprobe側で自動ロード抑制）。Wi-FiなしでP44 DebianがSSHまで達するか検証する。P25やP44の永続ファイルは変更せず、`kexec --load`に渡すRAM内の一時cmdlineだけを変更。**再試験前に残存pstore原本をraspi4へ取得し、UARTログ取得の稼働を確認すること**。もし成功すればWi-Fi probeが少なくとも今回観測されたpanicの直接要因であることが支持される。成功しなければ、PCIe/reset/clock/DTB初期化・rootfs等も追加で調査する。

現段階で`retry=0,success=1`、P26 ext4化、P25再署名を行わない。純正Bは現に起動しており、次の手動試験の独立復旧経路として保護する。

## 追記：再試験 Wi-Fi blacklist付きkexecロードPASS（2026-11-21）

純正Bへ復帰後、所有者が`quec_bootctrl -F`でC号機をslot A Debianへ戻し、Debianで同一P25を再度RAMステージングした。以下は**所有者の実機ログ**。

- `uname -r = 6.18.63-debian-t6-proto2`、`bootslot=a`、ルート `/dev/mmcblk0p44 ext4`。
- `python3 /root/cunit-kexec-g1.py inspect` PASS：P25期待SHA `74c1c98b31cdba54f71d16f1983fbeff347bb334c5ae7d7f1353cd57f734936e`、live FDT `177338 bytes`／`0ca607db163edd3422d6d526d457dfa3069b2c79b2300bd6539d34c6ec9d1806`。
- `stage` PASS：Image SHA `141b6750698cb362169cc150974b3464577d6ab5fa98aa941449fc3990c8ad00`、18,921,480 bytes。`/run/terminal6-kexec-g1`にRAM上のみ展開。
- 第2段に渡す一時cmdlineを`$(cat /proc/cmdline) module_blacklist=mt7996e modprobe.blacklist=mt7996e`に変更し、`kexec --kexec-syscall --load Image --dtb=live.dtb --append="$CMDLINE"`実行。`Can't open (/proc/kcore)`および`Can't get the symbol of _text`警告は出たが**終了コード0**。
- **`/sys/kernel/kexec_loaded = 1`**：Wi-Fi blacklist付き第2段イメージがカーネルにロードされたことを確定。
- **第2段への制御移行`kexec -e`はまだ未実施**。stage2 Linux起動の成否を推定しない。

次の安全ゲート：raspi4のUARTを**実際に記録していることをマーカーで検証**（`/dev/ttyUSB0`を二重に読まない）、バックアップ確認、書込みsync/可能ならrootfs ro、実験者の明示判断後に`kexec -e`。元のpstoreは`~/cunit-g1/pstore-after-g1.tar`として保存・SHA `7f3f439514019998331150f1427f1fe27d464c793371d84175c717af72c03a62`。

## 追記：Wi-Fi blacklist再試験用UART受信・保存PASS（2026-11-21）

raspi4で既存の`sudo cat /dev/ttyUSB0 | tee ...`が0バイトになっていた。プロセスがUARTを開いている間に別コマンドから`stty -F`を実行しても、再確認時に`speed 9600 baud`へ戻った。所有者は旧監視を終了し、次のように**同一オープンFDを保持した状態で115200bpsを設定して記録**する方式へ切り替えた：

```sh
sudo bash -c '
  exec 3<>/dev/ttyUSB0
  stty 115200 cs8 -cstopb -parenb -ixon -ixoff -crtscts raw -echo <&3
  stty -a <&3 | head -n 1 >&2
  cat <&3
' | tee ~/cunit-g1/g1-kexec-wifi-blacklist-uart-v2.log
```

C号機Debian`/dev/ttyS0`から`printf '\r\nG1-UART-V2-TEST-123456\r\n' > /dev/ttyS0`を実行後、raspi4が**62 bytes**を記録し、`CUNIT-UART-TEST-20261121`および`G1-UART-V2-TEST-123456`を完全受信した。**UART収録ゲートPASS。**

`kexec`前の残ゲート：現行C号機slot A/カーネル、`/sys/kernel/kexec_loaded=1`を再確認、rootfs P44を`sync`して可能な場合はro再マウント、手動復旧確認。**実際のWi-Fi blacklist第2段`kexec -e`はこの記録時点で未実施。** 元のpstore tarはraspi4にSHA保存済み。UART受信ターミナルは開いたまま保持。
