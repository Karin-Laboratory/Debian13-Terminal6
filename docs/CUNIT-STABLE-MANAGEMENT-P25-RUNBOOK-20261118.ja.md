# C号機 安定管理基礎P25 製造・復旧Runbook

> **2026-11-18 最新・憲章 v1.2優先：** 本文中のv1.0『初回は個別SSH公開鍵必須』は旧仕様。最新版は[設計憲章 v1.2](architecture/P25-FOUNDATION-POLICY.ja.md)と[初回セットアップ＋P44ペアの新決定](architecture/decisions/CUNIT-CHARTER12-INITIAL-SETUP-AND-PAIR-BUILD-20261118.ja.md)。物理隔離・空P44に限定して**初回だけ無認証root SSH（192.168.1.1:22）**、P44へDebianと認証を永続化して別セッションで検証後に閉鎖。通常SSH/救援SSHは認証必須。現在のビルドと実機受入の状態はそれぞれ別判定。

作成: 2026-11-18 JST / 対象: SoftBank Air Terminal 6 C号機、Debian 13、Linux 6.18.63
担当: `codex/cunit-stable-management-p25-20261118`
**状態: PUBLIC_HOST_BUILD=PASS / PRIVATE_MANUFACTURE=PASS / PRIVATE_RETENTION_AND_READBACK=PASS / C_UNIT_BOOT=NOT_TESTED / KEYED_RESCUE_SSH=BLOCKED。未署名、実機未操作。**

## 基準と引継ぎ

- [PR #21](https://github.com/Karin-Laboratory/Debian13-Terminal6/pull/21): 公開OSSからのARM64 Image・モジュール・32MiB unsigned P25製造は過去CIでPASS。既存candidateの実機起動保証ではない。
- [PR #23](https://github.com/Karin-Laboratory/Debian13-Terminal6/pull/23): PCIe/USBを有効化する試験DTB。新しい安定管理版には無条件に取り込まない。
- [PR #3](https://github.com/Karin-Laboratory/Debian13-Terminal6/pull/3): 100MHz/no-CQE、P44 ext4をC号機で実測。安定性の根拠は当時の対象ビルドと負荷条件に限定。
- [PR #1](https://github.com/Karin-Laboratory/Debian13-Terminal6/pull/1): privateドライバに依存した初期LANの沿革。今回の公開版は [public-management](../public-management/start-management.sh) のnetlink方式を採用し、private test23/test24に依存しない。
- [PR #19](https://github.com/Karin-Laboratory/Debian13-Terminal6/pull/19): 過去のKVM実機実証。新候補のKVM/LAN/SSH動作保証にはならない。
- [ハードウェア台帳PR #7](https://github.com/Karin-Laboratory/Debian13-Terminal6/pull/7): 実機検証済み・部分・未確認を区別する。2026-11-14の古い台帳は2026-11-18実測より優先しない。

2026-11-18実測はユーザー提供: C号機slot AでUARTログイン画面に到達したがARP/SSH不能。raspi4側eth0=192.168.3.71/24、1Gbps Full。stock B起動後は同経路でARP 3/3 PASS、`bootslot=b`、root shell。P44は未マウントのext4 `rootfs_data` 約2.5GiB。**stock BのARP成功をDebian LAN成功と読み替えない。** 故障原因は未確定。

## 設計憲章への準拠と保留差分

- [【旧版履歴】設計憲章 v1.0](architecture/P25-FOUNDATION-POLICY.ja.md)と[AGENTS.md](../AGENTS.md)を、`main` commit `ab0bd832d03d3ad47a2531a256ae9d26f34ffc0a`から**原文一致**でこの開発ブランチにも取り込んだ。憲章の条件自体は変更していない。
- 詳細は[憲章整合・初回SSH/IP差分記録](architecture/decisions/CUNIT-INITIAL-MANAGEMENT-CHARTER-ALIGNMENT-20261118.ja.md)を参照。所有者は**P44 Debianが正常起動した最初の時点で**`ssh root@192.168.1.1`（TCP/22、公開鍵認証・パスワード入力不要）できることを希望する。**P25/initramfs救援SSHまで22番に統一する要件は撤回**し、憲章§6どおり救援Dropbear（現候補TCP/2222）を別経路として扱う。P44通常SSHのauthorized_keys初回配備と両サービスのhost key/known_hosts管理、実通信は未実証。
- [純正slot B 調査 PR #27](https://github.com/Karin-Laboratory/Debian13-Terminal6/pull/27)では純正が`eth0.1`/`eth0.2`→`br-lan`、`eth1` DOWN、`lan2`なしと観測された。安定P25候補の`eth1`+`lan2`とは異なる。これは候補不動作の**原因確定ではない**が、UART/DT/MAC/PCS/DSAと双方向ARP/SSHで別途合格させる必要がある。
- 旧`192.168.3.0/24`は過去の隔離試験実測であり、憲章による初期値固定ではない。新`192.168.1.1/24`は家庭LAN`192.168.0.0/22`と重複するため**隔離専用**、移設時は再設計する。

## 安定版の基本方針

1. CPU/GIC/clock/reset/pinctrl、MMC 100MHz/no-CQE、P44 ext4/initramfs、UART、管理NETSYS/PCS/SGMII1/MT7531 DSAの起動依存をP44なしで利用可能とする。**今回のP25製造候補はbuilt-in `=y` を選択しCIで検査するが、設計憲章§4は同一P25のinitramfsに同梱するABI互換モジュールも認める。built-in強制は全将来版の原則ではない。** どちらも実ハードRX/TX/ARP成功の証明ではない。
2. P44で継続開発する拡張モジュールは、P25と同一ソース・同一ビルドから取り出し `Module.symvers`、`System.map`、`.config`、`kernel.release` とともに保存する。`scripts/verify-module-abi.py` で全 `.ko` のvermagicを照合する。
3. 緊急SSH: initramfsにARM64 Dropbearと実行に必要なライブラリを同梱する。鍵無しなら **fail-closed** とし、公開成果物に鍵を入れない。P44がマウント不能ならUART上のfail関数が救援起動を試行し、その後コンソールを残す。P44へのhandoffに成功した場合、C号機専用鍵と明示した隔離フラグのある時だけ、鍵・バイナリを一時RAM上の `/run/terminal6-rescue-root` へ引き継ぎ、systemd一時unitで通常SSHと別の **TCP/2222** を提供する設計。実通信・切替・再起動試験は未実施。
4. `/root/.ssh/authorized_keys` はraspi4の `~/.ssh/cunit-ed25519.pub` に対応する公開鍵を**非公開工程だけで**配置。秘密鍵はraspi4から移動しない。Dropbearホスト秘密鍵はC号機専用の継続固定鍵を非公開保持。通常Debian SSHはport 22の既存ホスト鍵を保持し、救援port 2222は別のknown_hostsエントリと指紋を事前検証する。 `StrictHostKeyChecking=yes` を変更しない。
5. **新しいC号機専用・隔離初期IPはOpenWrt標準の `192.168.1.1/24`**（`lan2@eth1`）。[初期CIDR設定](../configs/cunit-initial-management.cidr) を正本として、initramfs救援と、個体認証鍵・`ISOLATED_MANAGEMENT_ONLY` を備えた場合のP44 `systemd-networkd` 一時設定に引き継ぐ。家庭LAN `192.168.0.0/22` と重なるため、家庭LANに移す前に別の管理セグメントへ明示的に変更し隔離フラグを解除する。実機IPは今回変更しない。ブリッジ/NAT/DHCPサーバーの自動有効化は禁止。

## 非公開パーソナライズ

`scripts/stage-rescue-ssh.sh /absolute/new-rescue-stage` はARM64上のDropbearとライブラリを構成する。`TERMINAL6_RESCUE_PRIVATE_DIR` が未指定なら、SSH認証鍵とホスト鍵は入らず、起動拒否となる。**公開CIは意図的にこの状態を検査する。**

非公開工程はディレクトリに `authorized_keys`（秘密鍵ではなくEd25519公開鍵）、`dropbear_ed25519_host_key`（C号機専用秘密鍵）、隔離直結運用を有効にする `ISOLATED_MANAGEMENT_ONLY` を置く。必要な場合だけ `management-ip` に `IPv4/prefix` を与える。これらは公開リポジトリ、公開Actionsログ、公開成果物へ入れない。起動前に公開鍵、固定ホスト鍵の指紋・継続性を独立確認する。鍵の出所未確認なら `SSH_ACCEPTANCE=BLOCKED`。

**実機受入では** (a) P44が起動する場合の通常SSH、(b) P44ネットワークが失敗する場合のRAM救援port 2222、(c) P44をマウントできない場合のinitramfs救援、(d) UART、(e) reboot後の復帰、を個別に試験する。P44復旧経路を試すためだけに未承認のP44破壊操作をしない。

## 後付け機能と採否

| 群 | 現時点の基礎/証拠 | P25候補 | P44後付け / 未確定事項 | P25再製造 |
|---|---|---|---|---|
| 管理LAN, eMMC, UART | 公開OSS Kconfig/実験DTB、100MHz/no-CQE過去実測 | **P44非依存が必須**。今回LANはbuilt-in、将来は同一initramfs内の互換モジュールも可。実パケット未達 | PCS初期化順・DMA RX/TX・DSA管理ポートは実機ARP/SSHで検証 | 実測障害があれば必要 |
| Wi-Fi 2.4/5/6GHz | MT7996系カーネルとPHY部分証拠 | cfg80211/mac80211/mt7996eをmodule、PCIe基礎を保持 | 校正/PCIe電源/ファームウェア、合法な規制設定、実RF未確認 | DT/非module基礎修正時 |
| Bluetooth/ESP32 | ESP-AT経由BLEは実証、Linux HCI不明 | UART/TTY基礎を保持 | HCI transport/firmware解明、P44 userspace | DT基礎変更時のみ |
| GNSS | stock側報告あり、C Debian port未完 | module基礎を維持 | conninfra/export/SMC契約未確定 | 組込必須依存が出たとき |
| USB | P44上の一時モジュール登録の過去記録 | xHCI/PHY/USB storage等module | VBUS、電源、DTリソース、実データ通信は未確認。新PCIe/USB有効化DTBを今回採用しない | DT有効化検証後 |
| PCIe | MT7996関連経路が候補 | 公開host/PHY基礎を保持 | BAR/PHYリセット/電源・port機能は実機確認要 | DT修正時 |
| I2C, SPI, SPMI | stockのI2C client等の台帳 | 共通基礎を有効化できる範囲 | bus controller、clock/reset/PMIC固有依存未解明 | 必要なDT/builtin時 |
| PWM, GPIO, fan, LED | fan一時モジュール実績、GPIO対応未確定 | GPIO/pinctrl基礎保持 | LED expander、GPIO方向、fan tach/安全性未確定 | pinctrl等変更時 |
| RTC, thermal, sensor, TRNG/crypto | 一部APIあり、RTC/TRNG未確定 | 汎用基礎のみ | DT compatible/PMIC配線を推測で追加しない | DT/SMC変更時 |
| KVM | 過去の実機KVM起動PASS、今回P25未検証 | PR21 capableの `KVM=y` を容量内で保持 | P44 QEMUなど。LAN優先、仮想化機能を実機PASSとしない | サイズ/安定性との衝突時 |

## 製造と検証

専用[CI workflow](../.github/workflows/cunit-stable-management-p25.yml)は公開PR #21の製造工程を再利用し、ARM64 native build、再現可能initramfs、Dropbear同梱（鍵無し起動不可）、必要Kconfig、Image 35MiB上限、正確に32MiBのunsigned boot-v2、構造・DTB・payload・全量SHA、同一ビルドmodules/vermagicを検査する。公的CIには個体鍵やraw firmwareイメージをアップロードしない。

**結果記録の原則:** CIが成功しても `HOST_BUILD=PASS`、`P25_READBACK=PASS` など製造ゲートだけを記録。 `C_UNIT_UART_BOOT`、`C_UNIT_LAN_ARP`、`C_UNIT_SSH_NORMAL`、`C_UNIT_SSH_RESCUE`、`C_UNIT_COLD_BOOT` は別途署名済み候補の実機試験まで `NOT_TESTED`。鍵無し公開P25では緊急SSH受入は `BLOCKED`。

## 署名・保存・禁止事項

次工程に必要なもの: 実物unsigned P25 33,554,432 bytes、kernel Image/Image.gz、DTB、initramfs、same-build modules、.config、Module.symvers、System.map、kernel.release、source input receipts、ビルドログ、抽出/検証結果、**全量SHA256**。非公開保管先で読み戻して完全一致を確認し、公開CIのSHAを非公開再製造品のSHAと混同しない。個体固有の鍵・calibration・ベンダー由来イメージは必ず非公開にする。

**禁止:** 署名、実機へのwrite、P25/P26/P44/GPT/bootcontrol変更、slot切替、再起動、純正slot B上書き、旧KVM P25上書き、6GHz RF送信。過去署名承認は新SHAへ継承されない。保存が未達なら `PRIVATE_RETENTION=BLOCKED` とし、保管URLを捏造しない。

## 2026-11-18 公開製造実績（実行後追記）

- [実CI #44207428296](https://github.com/Karin-Laboratory/Debian13-Terminal6/actions/runs/44207428296): **SUCCESS**。
- 入力公開ソースコミット: `9128d92d445b3753ca605aea85ffcd9f6190a50e`。
- 非圧縮ARM64 Image: **15,153,160 bytes**、Image.gz: **9,402,256 bytes**。35MiB上限PASS。
- same-build ABI: `6.18.63-t6-public-capable`、40モジュールすべてvermagic照合PASS。Module.symvers/System.map出力PASS。
- 公開unsigned boot-v2 P25: **33,554,432 bytes**、SHA256 `54efbe6721393dbaaf36143ba188d569df767f961d65931c43fb3a0add8ba40c`、独立32MiB全量readback PASS。
- Dropbearバイナリ/依存libsのinitramfs格納、同一入力からのinitramfs一致、**鍵なしfail-closed** 検査PASS。ただし公開・非公開ともC号機鍵の認証ログイン、管理LAN実パケットは未試験。
- 限界: P44のマウント不能およびP44ネットワーク障害に備える構造。 `switch_root` 後にsystemdそのものが停止する故障モードは**復旧未保証**。別の実機受入を要する。
- 公開CIのSHAは **個体鍵を含まない公開製造品** のもので、非公開保存版・署名対象値とは混同しない。

## 2026-11-18 非公開保存の最終検証

- 非公開担当[PR #172](https://github.com/Karin-Laboratory/SBAT6A-Offline-Archive/pull/172) と [Draft Release ID 449370879](https://github.com/Karin-Laboratory/SBAT6A-Offline-Archive/releases/tag/untagged-d5f27f3715b64e0f2ca1) に、公開ソース `9128d92d445b3753ca605aea85ffcd9f6190a50e` からネイティブARM64で製造したunsigned P25を保存。
- 非公開製造[run #44207666720](https://github.com/Karin-Laboratory/SBAT6A-Offline-Archive/actions/runs/44207666720) でImage/モジュール/P25独立製造とReleaseへの14アセット保存までPASS。ただしDraftタグでの最終ghダウンロード失敗により、run全体はFAILURE。保存失敗ではない。
- 再取得専用[独立CI #44209377382](https://github.com/Karin-Laboratory/SBAT6A-Offline-Archive/actions/runs/44209377382) は **SUCCESS**。Draft Releaseの14アセットすべてをGitHub APIのasset IDで再取得し、各サイズ・全バイトのSHA256をGitHub保存記録と照合。P25は製造時の独立レシートとも一致。40件の同一ABIモジュールを確認。
- **非公開保存P25: 33,554,432 bytes / SHA256 `353533d88ff76b22cb324ec95230ed6bf2da683026a1a227a7c5fbcecc1e9a2b`**。Release P25 asset IDは `761233573`。非圧縮Imageは15,153,160 bytes。module tarは3,061,760 bytes。
- **このSHAは鍵なし非公開製造候補の識別値**。公開CI SHA `54efbe6721393dbaaf36143ba188d569df767f961d65931c43fb3a0add8ba40c` と区別。ユーザー指定のraspi4 Ed25519公開鍵やC号機専用Dropbearホスト秘密鍵は入っていない。したがって緊急SSHの実認証が受入未達で、署名・起動承認には進めない。鍵を入れる個体専用パーソナライズ後は、新しいイメージの全量独立SHAを改めて取得する。
- **SIGNED=NO / FLASH=NO / SLOT_CHANGE=NO / REBOOT=NO / REAL_ARP_SSH=NOT_TESTED / RF=NO**。純正slot Bと旧KVM P25を一切変更していない。

## 2026-11-18 履歴：v1.0時点の初回IP/SSH指示（v1.2で一部失効）

- 目標: **個体専用鍵を事前配備し、C号機のP44 Debianが最初に正常起動した時点から**、隔離した管理ポートで `ssh root@192.168.1.1` （通常SSH TCP/22）に公開鍵認証でパスワード入力なしにログインできること。P44未起動時はこのコマンドの成功を要求せず、救援SSHの検証を別ゲートに分ける。標準IPは[OpenWrt公式SSHガイド](https://openwrt.org/docs/guide-quick-start/sshadministration)を確認。
- 設定値の正本: [`configs/cunit-initial-management.cidr`](../configs/cunit-initial-management.cidr) の `192.168.1.1/24`。初期P25側の救援LANは同じIP、P44へ正常に移行した場合も `/run/systemd/network/10-cunit-isolated-management.network` を一時生成して `lan2` に同じIPを割り当てる。これはP44ディスクのネットワーク設定を書き換えない。
- **安全ゲート:** C号機専用公開鍵、継続固定SSHホスト鍵、`ISOLATED_MANAGEMENT_ONLY` を非公開工程で準備した場合だけP44への静的IP注入を有効化。鍵のない公開版は非公開鍵なしでログイン可能にしない。既存家庭LANとの重複を避け、隔離ケーブルまたは独立したネットワークを用いる。
- **raspi4接続条件の変更:** 2026-11-18時点のraspi4 `eth0=192.168.3.71/24` は旧実測。新IPへ接続する試験時は、専用NICに一時的に例 `192.168.1.2/24` を設定する等、経路を事前確認する必要がある。今回はraspi4のアドレスや実機設定を操作していない。
- **憲章準拠の最終決定（2026-11-18）:** ②は通常Debian SSHをTCP/22、救援Dropbearを別のTCP/2222とする。P25からP44へ**同一TCP/22を連続待受する要件はなし**。各モードの認証鍵、ホスト鍵、known_hosts、起動/停止・復旧条件を分けて検証する。③はbuilt-inかP25/initramfs内の互換モジュールかを実測に応じて選べる。現候補はbuilt-in選択を維持するが、恒久必須ではない。P44初回正常起動時のroot公開鍵ログイン、鍵・host key継続性、実ARP/SSH・再起動は `BLOCKED/NOT_TESTED`。IP設定のみでは受入PASSとしない。
- **不変の既存成果:** この変更は前回の保存済みunsigned P25の32MiBデータやSHAを変更しない。新設定を組み込んで再製造するP25は**別ファイル／別SHA**となり、検証後に別途署名承認が必要。今回、署名・実機書込み・slot切替・再起動は禁止。

## 2026-11-18 最新：v1.2 初回導入と署名なしP25/P44ペア製造

詳細な実装・未達・操作手順は[独立した決定・実装記録](architecture/decisions/CUNIT-CHARTER12-INITIAL-SETUP-AND-PAIR-BUILD-20261118.ja.md)を正本として参照する。この節は従来のv1.0履歴より優先し、**CI成功でも実機受入にはならない**。

1. **P25:** `initramfs/init`が既存P44を読み取り、`lost+found`と専用`.terminal6`しかない空ext4のみ、起動前の独立管理SSHを有効にする。`terminal6-firstboot serve`は`192.168.1.1:22`のDropbear `-B`とinitramfs RAMだけの空rootパスワードを使用する。P44未マウント、既存データ、Debianインストール済み、完了マーカーありの場合、無認証SSHは**起動しない**。
2. **ホスト鍵:** 公開P25に共有秘密鍵を入れず、機器ごとにEd25519を生成してP44`/.terminal6/ssh`に保存。後続のOpenSSHへ`dropbearconvert`で引き継ぐ。UART指紋照合は実機受入条件。
3. **P44導入:** [rootfs製造](../scripts/build-public-p44-rootfs.sh)はGNU tarの所有者・権限・ACL・xattrsを保存し、デフォルトrootパスワードをロック。`P44-install.zip`は同じビルドのmodules、rootfs.tar.gz、P25のunsigned SHA、kernel.releaseと内部SHAを固定。対象P44を上書きせず、[導入スクリプト](../scripts/install-p44-initramfs.sh)は外部で照合したZIP SHA、空P44、内部SHAとkernel.release一致を確認してから展開する。失敗時の自動初期化は禁止。
4. **初回認証から通常SSHへ:** P44のrootパスワードまたは公開鍵を永続設定。通常OpenSSHは`PermitEmptyPasswords no`。検証専用のP44 TCP/2223へ**別セッションから認証付き再接続**でき、P44に検証マーカーが残った場合だけ`terminal6-firstboot finalize`で無認証22番の受信を閉じ、P44通常22番へ引き継ぐ。救援2222番は従来どおり**鍵認証限定・fail-closed**。
5. **設計上の限界:** ZIP正式配布の真正性署名、実LANパケット、Dropbear空パスワードの実接続、P44展開・鍵継続・認証切替、電源断・再起動・復旧は未検証。P44を完全再フォーマットしたときの初期モード再有効化防止は独立の来歴管理が必要になり得るため**BLOCKED**。家庭LAN`192.168.0.0/22`は初期`192.168.1.0/24`と重なり、物理直結・隔離以外では使用しない。
6. **署名承認は含まれない:** 署名なしP25とP44 ZIPのホスト製造だけを依頼範囲とする。正式リリース仕様の『署名済みP25＋P44 ZIP』を満たしたとは宣言しない。個別の署名、C号機書込み、slot切替、再起動、RF送信は行わない。

