# Stock UART / LK / Emergency Shell / P43・P44 共通入口

Debian on Air Terminal 6 の導入前に必要になる、**純正slot B側のUART・Linux shell・eMMC・分割準備に関する公開可能な実機知見**は、OpenWrt側の共通資料を正本とする。

- [初期準備の共通入口（初めて触る人・AI向け）](https://github.com/Karin-Laboratory/openwrt-terminal-6/blob/main/START-HERE.ja.md)
- [人間向け初期準備の流れ・P43未マウントの考え方](https://github.com/Karin-Laboratory/openwrt-terminal-6/blob/main/docs/COMMON-INITIAL-PREPARATION-HUMAN-GUIDE.ja.md)
- [2026-11-17実機成功：純正B＋SSHでホスト側P43オフライン縮小・P44新設の詳細（第三者書込みBLOCKED）](https://github.com/Karin-Laboratory/openwrt-terminal-6/blob/main/docs/P43-P44-STOCK-SSH-OFFLINE-SHRINK-20261118.ja.md)
- [初期準備と公開方針（公開範囲・正本の所在）](https://github.com/Karin-Laboratory/openwrt-terminal-6/blob/main/docs/COMMON-INITIAL-PREPARATION-PUBLICATION.ja.md)
- [日本語の実測知見と注意点](https://github.com/Karin-Laboratory/openwrt-terminal-6/blob/main/docs/STOCK-UART-EMERGENCY-P43P44-EVIDENCE-20261113.ja.md)
- [AIエージェント向け機械可読の観測情報](https://github.com/Karin-Laboratory/openwrt-terminal-6/blob/main/docs/STOCK-UART-P43P44-EVIDENCE-20261113.json)

**正本はOpenWrt公開リポジトリのmainを参照。**

## 一般化できることと、できないこと

- 共通化できる知見: UART 115200 8N1、LKとLinuxシェルの区別、Emergency ShellのPID1確認、純正B Linux 5.4.238の実測、P43/P44の概要、ext4とGPTは別のサイズ単位で扱うこと。
- 共通と仮定しない値: eMMCデバイス名、GPT GUID/LBA、MAC、SSH鍵・認証設定、ファームウェアバージョン、P43空き容量、既にP44があるか。
- 純正BでのSSH接続実績はあるが、**初期状態の中古機でSSHを新規開通し再起動後まで永続化する一般的手順は未立証**。
- 2026-11-17に第4号機でP43縮小・P44新設・再起動後の永続性を実機確認した。ただし最終適用はlazy detachを使用しin-use警告も記録されたため、**第三者の未分割実機で安全に完走する手順は未立証**。

## 位置づけ

この資料はDebian本体のインストール手順ではない。人間・任意のAIエージェントが、Linux/WindowsからUARTで物理接続した後の既知の事実を再利用し、足りない部分だけを現物で調査するためのもの。未検証の端末書込みを自動許可するものではない。

個体固有データ・秘密鍵・未公開の脆弱性・純正ダンプなどを転載しない。新たな観測は事実・推測・未検証を区別して匿名化する。
