# eMMC障害・変更・復旧記録

## 観測の順序

1. 実機はDebian 13、root=P44 ext4 RW、既存Ethernet/SSH/NATで稼働。
2. APTで診断ツールを導入。シミュレーションに大量の依存が出たgpsd-clientsは導入対象から除き、必要な小さいCLI群を`--no-upgrade --no-install-recommends`で選択。既存kernelの更新なし。
3. 約10:13:29 JSTのkernel journalに`msdc_cmdq_irq: DATA TIMEOUT ERR`、dat_err=-110、CQE recovery、P44 write I/O error、ext4 unwritten extent変換失敗が出た。
4. 管理接続が応答しなくなり、約10:16台に再起動後のSSH復帰を確認。原因を特定するpanic traceは得られず、再起動の直接トリガーは未確定。意図的なreboot/resetコマンドは実行していない。
5. 新bootでext4 journal replayとorphan回収を確認。eMMCはmmcblk0からmmcblk1へ変わったが、コントローラは引き続き0x11230000。P44 handoff/管理network/SSHは復帰。
6. 中断されたbluez/QMI/MBIM等の設定を`dpkg --configure -a`で完了（終了0）。今回作った一時policy-rc.dは撤去し、`dpkg --audit`空を確認。
7. `dpkg -V`で新規導入のmbimcliとPython _codecs_twの2ファイルのMD5不一致を検出。mbimcli先頭はゼロ化され実行形式エラーだった。
8. 保持済み同版debから/tmpではなくRAMの/runへ該当2ファイルだけ展開。パッケージ台帳のMD5一致を確認して配置し直したが、ファイル`sync`はI/O errorを返し、CQE/write/ext4障害が再発。
9. 後続の読み取りでは2ファイルのMD5は一致、mbimcli --versionとPython big5 codecが成功し、`dpkg -V`も空。しかしpage cacheを経由するため**永続媒体への修復完了ではない**。追加書き込みを停止。

## 維持できたもの・未確認

調査末尾でSSH、networkd、UART getty、timesyncdはactive。公開鍵とsshd設定の変更前ハッシュ一致。ping 1.1.1.1は3/3、DNS成功。メモリ空きは十分で、OOMの直接証拠はない。rootfsはRW表示だが、これは書き込み健全性の証明ではない。

P25/P26/GPT/純正Bの意図的変更、MMC controller再初期化、CQEのruntime切替、fsck修復は行っていない。既存boot-successサービスは観測された再起動時に従来の処理を実行したため、P1が不変だったとは主張しない。

## 保存と復旧の境界

診断ログ、DT、テスト候補は開発VMへ保存。以降はstdinからcodeを実行しstdoutをVMへ回収し、P44へ収集ログを置かない。最初にP44へ転送した収集スクリプトは障害後0 bytesだったため、P44に保存した成果物を正本にしていない。

APTによる追加パッケージと版は[一覧](evidence/CUNIT-TOOLS-20261114.txt)。カーネル・既存network設定・UART設定は交換していない。導入時にpolicy-rc.dでサービス起動を抑え、終了後は撤去済み。BlueZ packageはunit有効化リンクを作ったが、BT無効のkernelなのでHCI機能は追加されていない。

P44への書き込みが不安定な状態で大量のapt remove/reinstallやバックアップ復元を繰り返すことは避けた。rootfsの完全なrollback・整合性修復は未完であり、[eMMC対策と次サイクル](CUNIT-EMMC-MITIGATION-20261114.ja.md)を先に実施する。保持済みdebと/runの限定復旧材はあるが、電源断後の完全性を保証しない。

別の救出環境からP44を未マウントで検査し、必要なデータを救出してから修復する。稼働中rootfsへのfsck修復や、純正Bのバックアップを検証せずにboot切替を行わない。
