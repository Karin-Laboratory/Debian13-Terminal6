# C号機 Debian 13：設計憲章 v1.2 に基づく初回導入とペア製造の実装判定

記録：2026-11-18 JST／採用された憲章： [P25安定基礎設計憲章 v1.2](../P25-FOUNDATION-POLICY.ja.md)（`main` 原本）、[AGENTS.md](../../../AGENTS.md)。これらの文書自体は変更しない。

## 変更理由

以前の[憲章v1.0整合記録](CUNIT-INITIAL-MANAGEMENT-CHARTER-ALIGNMENT-20261118.ja.md)は、その後の所有者決定で**設計史料に移行**した。v1.2の§6は明示的に、最初の未設定個体では物理隔離された有線管理LANだけでOpenWrt型の**root無認証SSH（TCP/22）**を採用する。以前の「C号機の個別authorized_keysをイメージへ埋め込まなければ初回SSH不能」という基準は新仕様に適合しない。

v1.2の§8Aは、正式配布単位を**署名済みP25 + P44-install.zip** の対応ペアとする。ただし今回のユーザー依頼は最新設計に基づく製造であり、個別SHAへの署名・実機書込み権限を追加しない。**unsigned P25 + experimental P44 ZIP** の製造・検証を先に行う。

## 実装した候補と制限

1. [`scripts/firstboot-initramfs.sh`](../../../scripts/firstboot-initramfs.sh) と [`initramfs/init`](../../../initramfs/init): P44のext4をマウントし、`lost+found`と専用`.terminal6`領域以外に既存ファイルがないこと、`/sbin/init`と完了マーカーがないことを検査する。**これらが揃う場合だけ**、initramfs RAM上のroot空パスワード、Dropbear `-B` のTCP/22を `192.168.1.1` に束縛して立ち上げる。P44マウント失敗、既存Debian、想定外データ、完了マーカーでは起動しない。物理的なLAN隔離は利用者の責任であり、同一L2の第三者もrootになれる。
2. **初回ホスト鍵:** 実機起動時に`dropbearkey`で個別Ed25519ホスト鍵を生成し、P44`/.terminal6/ssh`へ永続化。公開P25/ZIPに秘密鍵は含めない。導入時`dropbearconvert`でOpenSSH形式へ変換して通常sshdへ引き継ぐ。ホスト鍵の指紋をUART等で独立照合する。
3. [`scripts/package-p44-install.py`](../../../scripts/package-p44-install.py): 同じCIビルドから、uid/gid/権限/ACL/xattrsを維持するGNU tar rootfs archive、同一カーネル`.ko` tar、正確なP25 unsigned SHA、kernel.release、各ファイルSHA256/サイズをマニフェストに固定し、導入用ZIPに格納する。ZIP自体にはP25を複製しない。**公開用の署名済みP25ペアではない。**
4. [`scripts/install-p44-initramfs.sh`](../../../scripts/install-p44-initramfs.sh): 物理隔離下で明示的に転送したZIPに対し、**信頼済み配布元から別途確認したZIP SHA256**を照合。ZIP内の固定ファイル群と各SHAを独立確認し、実行中kernel.release一致を確認した後に限って**空P44**へGNU tarで展開する。既存データ/インストール済みP44は自動上書きしない。途中失敗はUARTによる要診断、再試行を自動化しない。
5. **資格情報:** P44へ導入後、`terminal6-firstboot passwd`でchroot先Debianのrootパスワードを設定するか、P44`/root/.ssh/authorized_keys`に利用者公開鍵を設置する。未設定のパスワードはP44でロックされており、通常sshdは空パスワードを拒否する。
6. **二次接続:** `terminal6-firstboot verify` はDebianの本物のsshdを一時TCP/2223に起動する。利用者は**別のSSHセッション**で設定した資格情報を使ってログインし、P44`/.terminal6/auth-verified`を作成する。これとP44側認証・ホスト鍵ファイルの検査を通過したときだけ`terminal6-firstboot finalize`で永続完了マーカーを記録する。initramfsはこのマーカーを確認後に無認証22番の待受を終了し、通常P44へhandoffする。救援SSHは独立の鍵認証TCP/2222に限定する。
7. [`scripts/build-public-p44-rootfs.sh`](../../../scripts/build-public-p44-rootfs.sh) はDebian 13の正常運用SSHをパスワード**または**公開鍵で認証可能にし、`PermitEmptyPasswords no`、初期管理IP`192.168.1.1/24`。家庭LAN`192.168.0.0/22`と重複するため導入時は直結隔離する。

## 必須の注意と未検証ゲート

- **実機確認なし:** stock Bの実測は`eth0.1/.2`＋bridge、P25候補は`eth1`+`lan2` DSA前提。この差は未解明。物理パケット、ARM64/Linux実機起動、無認証ログイン、IP/NIC、SSH切替、再接続、P44展開、warm/cold bootは**NOT_TESTED**。CIの構造・製造検証で代替しない。
- **セットアップ失敗時:** P44が途中まで展開されたら無認証初期セットアップは自動では再起動しない。UART/純正Bから復旧状況を確認し、データを消さずに対処。誤ってP44を再フォーマットした場合、空領域と未使用個体の区別に別の不可逆マーカーが必要なため、**無認証モード再有効化防止の全故障モードは未実証**。従って実機受入の前に追加の安全設計・試験が必要。
- **SSH空パスワードの成立:** Dropbear `-B` が当該配布版とOpenSSHクライアントで無入力接続になるかは**通信試験待ち**。オプションの存在だけで合格としない。
- **P44の属性保存:** rootfsは`GNU tar --xattrs --acls`、導入もinitramfsに同梱したGNU tarを使用。実ファイル能力・ACL・symbolic link・numeric ownerの復元はホスト及び実機で独立検証が必要。
- **正式配布不可:** SSH認証切替の実機合格、署名済みP25、ZIP真正性のための署名付きmanifest/信頼経路、合法的な一般配布権限は未確定。CIが成功しても一般向け安全なP25/P44ペアと称しない。
- **操作禁止:** 所有者の別SHA個別承認なしに署名、P25/P26/P44/GPT/P43書込み、slot切替、再起動、無線送信、純正slot B変更を行わない。

## 想定する隔離導入操作（受入前の候補、実機未検証）

1. Linux管理PCをC号機へ物理直結し、C号機とは別の`192.168.1.0/24`アドレスを設定する。UARTで個体ホスト鍵指紋を確認する。
2. `ssh root@192.168.1.1` に初回ログインし、転送先`/newroot/.terminal6/inbox/P44-install.zip`へZIPを転送。接続した同じL2からの不正rootログインも可能な状態なので家庭LANを使わない。
3. `terminal6-install-p44 /newroot/.terminal6/inbox/P44-install.zip <信頼済みZIPの64桁SHA256>` を実行。パッケージ内に署名済みP25は入っていない。
4. `terminal6-firstboot passwd`、またはP44 `/root/.ssh/authorized_keys` を設定して権限を適正化。
5. `terminal6-firstboot verify` 後、別の接続から `ssh -p 2223 root@192.168.1.1` に**設定した認証**でログインし、`touch /.terminal6/auth-verified`。
6. 初期セッションで`terminal6-firstboot finalize`。保存・閉鎖後に通常Debianへ切り替わったら、通常22番へ再接続し、無認証rootを拒否することを確かめる。

この手順は設計上の候補であり、実機への適用手順としての公開は一連の受入試験後に行う。
