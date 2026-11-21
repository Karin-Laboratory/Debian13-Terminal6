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
