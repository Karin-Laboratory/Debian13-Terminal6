# C号機 ② Debian 13 / PR #41：P44 switch_root → PID 1終了の切り分け（2026-11-22）

## 実機事実・未確定事項

C号機の有限slot A試験は**1回で終了**。署名済みproto2 P25（全量SHA256 `74c1c98b31cdba54f71d16f1983fbeff347bb334c5ae7d7f1353cd57f734936e`）の書込みと、C号機・raspi4の独立32MiB readbackがPASS。Preloader/LKの旧`fdt_add_subnode` ASSERTは再現せず、Linux `6.18.63-debian-t6-proto2`、`DEBIAN13_T6_INITRAMFS_STARTED`、P44 rootfs、`DEBIAN13_T6_SWITCH_ROOT_P44`まで到達した。

その後、UARTではPID1終了 `Kernel panic - not syncing: Attempted to kill init! exitcode=0x00000100`。**exitcode 0x100は「PID 1が終了コード1」を示すが、switch_root BusyBox自身の終了か、systemd起動直後の終了かは連続したUARTエラーがなく未確定。** `/sbin/init`欠落・ELFローダー欠落を原因と断定しない。Debian userspace、LAN2、SSH、Wi-FiはNOT_TESTED。

有限試行後はstock slot B自動復帰。B `success=1`、ping 3/3、厳格ホスト鍵SSH、`boot_b`・`misc`保存SHA一致がPASS。P44はB復帰後未マウント、読み取り専用`e2fsck -fn` exit 0。**P44バイト同一性は未確認。** P44を意図的に再フォーマット、再展開、更新、修復はしていないが、A起動のmount/journal処理は除外できない。新たなrebootや試験、rootfs書込みは承認されていない。

- [実機記録：PR #41](https://github.com/Karin-Laboratory/Debian13-Terminal6/pull/41#issuecomment-7069277683)
- [記録の精度に関する追記](https://github.com/Karin-Laboratory/Debian13-Terminal6/pull/41#issuecomment-7069306132)
- [個体別証拠：非公開Chappie-Memory PR #27](https://github.com/Karin-Laboratory/Chappie-Memory/pull/27)
- 非公開raspi4 evidence：`/home/masataka/private/cunit-pr41-p25-swap-retest-20261122/`、UART rawのSHA256 `112203da8fac6bcc3f0be0877ea9a4b3b2509699b28d72a8c4ae8724bc417233`。公開リポジトリへ生データを複写しない。

**LK/FDT ASSERTの共通原因については別件`ON_HOLD / ROOT_CAUSE_UNRESOLVED`を厳守。** この電源サイクル後の1回の成功から電源断が原因だったと断定しない。①共通ローダーとは別の②系統として扱う。

## ZIPの事実と、実機P44の欠陥を混同しない

今回インストール済みP44の元候補は、非公開 ZIP `P44-install.zip` SHA256 `57058163645c0acfe7b9f5f760d7a2dc8af78fca33a81604a8d37d23c5815d3b`（187,389,339B）、private Release ID `453695494`、asset ID `775606937`。

既存の別のオフライン監査で**旧ZIP・新ZIPとも**以下が存在すると確認済み：
- `/sbin -> usr/sbin`
- `/usr/sbin/init -> ../lib/systemd/systemd`
- executable AArch64 ELF64 `/usr/lib/systemd/systemd`
- ELF `PT_INTERP=/lib/ld-linux-aarch64.so.1` と実体

しかし、ZIPが正しいという事実は**実際にC号機のP44に展開されたファイルのリンク・実行権限・バイトや動的依存、マウント条件**を証明しない。ext4のfsck成功もPID 1実行可能性を保証しない。P44交換やP25再署名を盲目的に行わない。

## 今回のコード修正

新しい`scripts/audit-proto2-p44-pid1.py`を追加し、以下を**全てread-onlyで検証**する：
- SHAを固定したowner-private ZIPの`rootfs.tar.gz`を**ホスト上に展開せず**ストリーミング走査
- `/sbin/init`の**中間symlinkを含むP44ルート内解決**（絶対リンクがホスト`/lib`に逸脱する誤検証を防止）
- 実行権限、ARM64 ELF64、`PT_INTERP`と動的ローダー実体
- `--root`で指定した実際のP44の同じsymlink鎖、systemdバイトSHA、ローダーSHAをZIPと比較
- `--root`は原則すでにマウント済みの**readonly mountpointだけ**を許可。`--offline-test-root`は隔離された一時テストrootfs専用
- ZIP・P44とも`/sbin/init`を実行せず、fsck、mount、chmod、chroot、書込み、rebootを一切実施しない

`tests/test_proto2_pid1_audit.py`に正しいsymlinkチェーン、絶対symlinkのゲストルート解決、ELF loader欠落、chmod欠陥、ZIP SHA差異、循環リンク等を追加。

`scripts/build-proto2-p44-rootfs.sh`のNative ARM64先行チェックも改善。従来の`chroot /usr/lib/systemd/systemd --version`だけでなく、**P25の本番エントリーポイントである`/sbin/init`**を引数のある安全なモードで実際に解決・実行して確認。ただしsystemdは`argv[0]=init`時に`--version`を受け付けず**`unrecognized option '--version'`と終了コード1を返す場合がある**。これはdynamic loader実行失敗ではない。新チェックは既知のoption parser到達を確認する。`/sbin/init`を通常モードで起動しPID 1を偽装することはしない。

このCIが通っても、**実機にあるP44に対する修復完了や、Linux PID 1成功の証拠ではない**。

## 最小の次の切り分け

**独立したC号機read-only操作承認後**、①②排他利用を確認してstock BからP44 PARTNAMEを確認。既知の安全手順で`-o ro,noload`の一時マウントを行い、`/sbin/init`の実体、symlink、mode、ELF interpreterと依存ライブラリを記録。比較ZIPは別環境で正確な完全SHAを検証しておくこと。

Python3のある**隔離診断環境**での概念例（実機Stock BにPython3が存在するとは仮定しない）：

```sh
python3 scripts/audit-proto2-p44-pid1.py \
  --zip /private/verified/P44-install.zip \
  --sha256 57058163645c0acfe7b9f5f760d7a2dc8af78fca33a81604a8d37d23c5815d3b \
  --root /mnt/readonly-p44
```

**成功判定は`installed_P44=PID1_AND_INTERPRETER_BYTE_MATCH_PASS`まで。** すべてのDT_NEEDED共有ライブラリ、ACL、cgroupとsystemd実行時要件、実機のP25 mount/switch_rootの成否を証明しない。ZIPと一致したら生UARTの`switch_root`近傍を時系列で比較し、`ENOENT`/`EACCES`/`ENOEXEC`、noexec、PID1実行後のstderrなどから未達を決める。実機P44とZIPが異なる場合のみ、差分と所有者許可に基づく**最小修正**を別途検討する。

今回、実機への読取り・書込み、P44修復、P25署名、boot control更新、電源操作、Wi-Fi/RF動作は実施しない。

## 2026-11-22 製造・検査 最終結果

**修正ソースの検証は全ゲートPASS。実機P44修復は未実施。**

- [公開新CI #44952266800](https://github.com/Karin-Laboratory/Debian13-Terminal6/actions/runs/44952266800)：**SUCCESS**。8件のread-only／異常系Pythonテスト、旧PR #41ソーステスト全件、ネイティブDebian ARM64新規debootstrap、canonical systemd `--version`・`/sbin/init`互換モード引数処理・新P44 tar製造までPASS。
- [既存P44 source workflow #44952271276](https://github.com/Karin-Laboratory/Debian13-Terminal6/actions/runs/44952271276)：**SUCCESS**。source-only安全試験、ネイティブARM64 rootfs生成、owner-neutral tar検証PASS。
- [非公開既存P44実物ZIP監査 #44952019666](https://github.com/Karin-Laboratory/SBAT6A-Offline-Archive/actions/runs/44952019666)：**SUCCESS**。保存済み候補 `570581636...` の全量SHA、非公開 ZIP→一時展開rootfsのPID1/ELF/loader一致、native dynamic loader・`/sbin/init`コマンドの実行パス検証PASS。
- [開発Draft PR #45](https://github.com/Karin-Laboratory/Debian13-Terminal6/pull/45)、[非公開監査Draft PR #193](https://github.com/Karin-Laboratory/SBAT6A-Offline-Archive/pull/193)。

上記はいずれも**本番C号機のP44現物のファイル一致、systemdがPID1として起動し続けること、FDT、LAN、SSHの正常性を証明しない**。署名済みP25を再署名する理由もない。P44の初期化・再展開を含む新しい配布イメージはまだ製造・適用していない。原因特定後に必要な最小変更だけを別ゲートで行う。
