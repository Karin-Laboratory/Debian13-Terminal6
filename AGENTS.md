# AGENTS.md — Debian 13 on Air Terminal 6

このファイルは、このリポジトリを担当するCodex・その他AIエージェントの**作業入口**です。技術的な設計判断の正本は[**P25安定基礎の設計憲章**](docs/architecture/P25-FOUNDATION-POLICY.ja.md)です。

## 作業開始時の読み込み順

1. [P25安定基礎の設計憲章](docs/architecture/P25-FOUNDATION-POLICY.ja.md)（main最新版、適用版/commitを記録）。
2. [README.md](README.md)と関連する既存Runbook、担当PR/ブランチ/CI。
3. 作業対象の最新の実測・既知の失敗と復旧記録。必要なら[ハードウェア調査](docs/hardware/README.md)や[共通準備・復旧入口](docs/COMMON-STOCK-UART-P43P44-ENTRY.ja.md)を確認。
4. 変更前に他担当の作業範囲と競合を確認。mainとDraft PRの成果を混同しない。

## 全担当に適用する設計原則

- **P25は起動・管理・復旧の基盤、P44はDebian通常運用と追加機能の場所。** ただし将来のP25再製造を禁止しない。
- 起動・管理・ストレージの健全性をWi-Fi/USB/KVM等の拡張機能より優先する。
- LANのbuilt-in化は選択肢の一つ。initramfs内に同梱した同一カーネルABIのモジュールでもよい。P44依存を排除し、実パケット通信で受入判定する。
- カーネル・Device Tree・initramfsと、P44のモジュール一式は互換性のある組として版管理する。`vermagic`一致のみで動作保証としない。
- Device Treeのunknownなboard電源・clock・reset・pin設定を推測して有効化しない。
- P44側の追加機能を可能な限りモジュール化する。ただしカーネル/DTB更新が必要な場合を拒否しない。
- **初回導入は方式B（Codexまたは人間の手作業）**：**専用の外部インストーラ・導入ツールは作らない。** 純正Bまたは検証済み復旧環境から、所有者が個別承認した対象`boot_a`へ署名済みP25を`dd`等で書込み、`P44-install.zip`のrootfs tarと対応モジュールを既存LinuxコマンドでP44 ext4へ配置する。PARTNAME/SHA/空P44/既存データ保護/読戻しをRunbookで検証。**P25/initramfsにもインストーラを要求しない。P44空/不正時は無認証SSHを開かずUART/認証付き救援へ。** [方式B決定記録](docs/architecture/decisions/CUNIT-EXTERNAL-P44-INSTALL-METHOD-B-20261118.ja.md)。
- **公開配布版の初回認証だけ**は所有者がOpenWrt型無認証root SSHを採用。事前にP44へ導入した**Debian上**で、物理隔離有線LANの`ssh root@192.168.1.1`（TCP/22）を初回だけ許す。利用者がDebian上で`passwd root`または公開鍵登録し、個別認証を検証したら無認証経路を閉じる。通常運用と救援SSH（TCP/2222）は個別認証必須。[憲章§6](docs/architecture/P25-FOUNDATION-POLICY.ja.md)と[初回認証決定記録](docs/architecture/decisions/CUNIT-FIRSTBOOT-SSH-OPENWRT-STYLE-20261118.ja.md)を参照。
- **公開Debianの配布単位は対応する署名済みP25＋P44導入パッケージのペア**。P44のrootfsはLinux属性を保持するtar等をZIP容器へ格納し、対応モジュール・manifest・ハッシュと互換性を検証する。初回インストールと既存P44更新を混同せず、既存データ/鍵を自動上書きしない。詳細は[憲章§8A](docs/architecture/P25-FOUNDATION-POLICY.ja.md)。
- 純正slot B、P26、P43、P44、GPT、boot control、秘密・個体校正を無断で変更しない。
- 6GHz等のRF送信は法令・機器認証・regdb・施設条件の確認を別途必要とする。

## 検証・権限の境界

- ホストビルド、32MiB unsigned P25の全量検証、非公開保全、署名済みファイル、実機起動、UART、ARP/IP/SSH、冷間再起動、復旧の各ゲートを区別して`PASS`/`FAIL`/`BLOCKED`/`NOT_TESTED`で報告する。
- 署名・実機書込み・slot切替・再起動・無線送信などは、作業対象と正確な入力を示して**必要な個別承認**を得る。過去の別SHAの承認を再利用しない。
- 公開できるOSSと文書のみをcommitする。privateイメージ、ホスト秘密鍵、端末認証情報、EEPROM/calibration、SIM情報を公開しない。
- 既存のOSS・成功実績を優先し、過去にPASSした工程を条件変化なしに無条件で繰り返さない。
- 実装・ビルド・試験・修正を完遂し、コミット/PR/CI/製造ハッシュと未達を正確に報告する。ハードウェア未検証を成功と断定しない。

## 設計憲章と実装の変更

- 憲章自体を変更する場合は、根拠、P44で代替できない理由、影響、復旧・検証計画をPRで示し、**所有者の明示的な承認**を得てから反映する。
- **実装PR/Runbookは日々更新してよい。** 実験の成功・失敗が憲章の自動変更を意味することはない。
- 個別プロンプトが憲章に反する場合、黙って書き換えず矛盾を報告する。特に起動基盤と救援経路を変更する前には安全ゲートを再確認する。
- 本`AGENTS.md`は入口・行動規則に絞り、重複した詳細設計を増やさない。技術原則の正本を憲章へ一本化する。
