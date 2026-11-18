# C号機 Debian 13：方式B（純正slot Bなどからの手動事前導入）

**正本：設計憲章 v1.4 §6/§8A。これは導入Runbookであり、書込み・署名・slot切替の承認ではない。**

## 構成

- ペア：対象個体へ書込み可能な**別途承認済み署名済みP25**（32MiB）と、対応する`P44-install.zip`。
- ZIP中身：`rootfs.tar.gz`（Debian 13 arm64 のLinux属性付きtar）、`modules.tar`（P25と同一カーネルビルド）、`kernel.release`、`manifest.json`、`SHA256SUMS`、本Runbook。
- **専用の外部インストーラは作らない**。既存Linuxの`unzip`、`sha256sum`、`tar`、`mount`、`findmnt`、`dd`等で人間またはCodexが対話的に導入する。ZIPを直接ext4へ展開しない。
- 現在の製造試作品は**unsigned P25と開発用P44 ZIP**。下記は署名済みP25が個別承認された場合の将来手順。**このRunbook自体は実機操作を許可しない**。

## 起動前の必須安全ゲート

1. C号機、slot Bの復旧可能性、純正B/旧起動資産のバックアップ、UART、停電時復旧方法を個別確認。対象を**パーティション名`boot_a`と`rootfs_data`**で特定し、容量や現在のマウントを照合する。デバイス番号`/dev/mmcblk0pXX`を想像で固定しない。
2. 署名済みP25の実物SHAと容量（33,554,432 bytes）、P44 ZIP実物SHA、manifest記載の**対応するunsigned P25 SHA**、kernel.release、modules ABIの整合を独立確認。ハッシュ一致だけで配布者の真正性を保証しない。署名済み版とunsigned版が別ハッシュであることを記録する。
3. P44のext4を**まずread-only**で調べる。`lost+found`以外の既存Debian、ファイル、認証鍵、設定、ユーザーデータがあれば**初回導入を中止**。空か不明でも止める。十分な空き容量とext4健全性を確認し、意図したP44以外の領域を変更しない。
4. 対象イメージの完全SHAと実機操作への**今回の個別承認**を得てから、P25の`boot_a`への書込み、全量readbackを実施。純正slot B、P26、P43、GPT、bootcontrolの変更は禁止（承認対象外）。
5. 承認・安全確認後、外部Linux環境でZIPを別の作業領域へ展開し、`sha256sum -c SHA256SUMS`を実行。Linux属性を保ったまま`rootfs.tar.gz`と`modules.tar`のみ、確定した空P44 ext4へ展開する。例：

```sh
# 以下はP44を正しく同定・マウント済み、書込み承認済みの場合に限る例
cd /temporary/verified-pair-content
sha256sum -c SHA256SUMS
cat kernel.release  # boot_a に書くP25のkernel.releaseと一致を確認
tar --numeric-owner --same-permissions --xattrs --xattrs-include='*' --acls -xzf rootfs.tar.gz -C /mnt/verified-empty-p44
tar --numeric-owner --same-permissions --xattrs --xattrs-include='*' --acls -xf modules.tar -C /mnt/verified-empty-p44
sync
```

6. P44の`/sbin/init`、`/etc/shadow`、初期systemdサービス、モジュール配置、UID/GIDと権限、ホスト鍵なし、バージョン/manifestを**読戻し**検証。ZIPを途中まで展開した場合、**自動再開しない**。現物を調べ、必要なら復旧手順を個別検討。
7. これらを満たし別途許可された場合だけslot Aを起動。LANは家庭LAN`192.168.0.0/22`から分離したケーブル直結`192.168.1.0/24`とする。初回SSHは**P25ではなくDebian P44**の`ssh root@192.168.1.1`（TCP/22、未設定時だけ無認証）。同じL2の第三者もrootになれるため、WAN/Wi-Fi/ブリッジ/NAT/DHCPサーバを使用しない。
8. Debian上で`passwd root`、または`/root/.ssh/authorized_keys`を登録し、`terminal6-p44-firstboot verify-start`後に別セッションから`ssh -p 2223 root@192.168.1.1`で**設定した資格情報による接続**を確認。そのセッションから`touch /var/lib/terminal6/firstboot-auth-verified`。初期セッションで`terminal6-p44-firstboot finalize`を実行して無認証22番を終了し、認証付き通常22番へ切替。二次接続・閉鎖・ホスト鍵一致を検証。
9. 再起動、電源断、P44故障の試験は独立承認・安全ゲートの下で実施する。P44が空・不正なら、P25はUARTに失敗を出し**無認証SSHを開かない**。救援TCP/2222は個体鍵と隔離条件がある場合だけ使える。

## 合格の境界

公開/非公開CIでP25が製造・ハッシュ一致しても、`LK起動`、`ARP/双方向IP`、`SSH初回無認証`、`認証切替`、`ホスト鍵永続`、`P44導入`、`cold boot`、`純正B復旧`は実機で独立に合格させるまでは**NOT_TESTED**。公開一般配布可否や署名・再配布権も別ゲート。
