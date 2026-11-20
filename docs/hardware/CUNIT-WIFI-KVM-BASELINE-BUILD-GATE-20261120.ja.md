# C号機 Wi-Fi対応P25/P44製造：既知良好KVMペアからの再製造ゲート（2026-11-20）

## 現状
**Wi-Fi対応の新unsigned P25/P44: 未製造。** この変更は誤ったベースを使って製造・署名しないための事前検証を追加する。P25への書込み、署名、再起動、RF送信はしていない。

### 成功した二種類の証拠を区別する
- **実機起動成功:** C号機 signed P25 SHA-256 `d8005468d4cb0b854d1b25e4abc9543bb5fb2348b7020eb70fe1febaea82a3a4`、復元P44 raw SHA-256 `9c49552566dc882529142b37deadac2dd2603c8d032933f18a7c917808404bfe`（復元時点の値。稼働中P44の生SHAとして扱わない）。Debian kernel.release `6.18.63-debian-t6-proto2`。LAN/SSH/MMC/KVMの実機PASSがある。
- **製造工程成功:** 公開PR #25、CI #44252500433、非公開CI #44252711731 と独立readback #44254184588。基準 `6.18.63-t6-public-capable`、ソースcommit `886d368f76e6305b3f10d67c61193aee61c7dd0c`。このP25/P44はC号機のKVM成功ペアそのものではなく、実機の起動成功は未証明。

前回の再製造では、成功FDTと同じSHAのFDTを使用していても、変更されたImageでMMC0 probe `-110` を実測した。このため**公開CIのsuccessを新KVM/Wi-Fi候補の起動可能性と取り違えない**。

## 追加したゲート
`scripts/verify-cunit-kvm-baseline-provenance.py` は非公開のJSON receiptで、既知良好P25/P44のサイズ/SHAと、成功版Image、resolved .config、Module.symvers、System.map、DTB、initramfs、kernel.release、パッチ順序記録の存在とSHA、およびsource revision/toolchain宣言を厳密に確認する。すべて不足なく揃わない限り非ゼロ終了する。読み取り専用で、ビルド、署名、書込みはしない。

必要な非公開receiptの構造は同スクリプトdocstring参照。作成時に所有者個体のバイナリ、ホスト鍵、校正情報、ファームウェアを公開しない。

## 次の製造作業（まだ未実施）
1. raspi4または非公開保管先から成功signed P25と復元時P44、同一ビルド由来の完全なkernel input一式を取得してreceiptを作る。すべてのファイルは独立SHAで確認。足りない資産はBLOCKEDと特定し、互換そうな別ビルドを流用しない。
2. 成功版のLinux Image再製造を**Wi-Fi無変更**で先に実行。ソース・ツールチェーン・パッチ・.config/DTB/initramfsを照合し、Imageバイト差があれば説明とMMC影響検証を要する。
3. その後cfg80211/mac80211/mt76（MT7990対応）をABI整合させ、同一ビルドのmodules、.config、Module.symvers、System.map、kernel.releaseを製造。まずKconfig/Kbuildとregdb整合を静的検証する。
4. **成功版FDTとinitramfsを固定**してboot-v2 `assemble-template-free-p25.py`、`verify-public-unsigned-p25.py`、`package-p44-install.py` の成功工程を新候補へ移植。P25 33,554,432 bytes、対応P44 ZIP manifest/内部SHAを検査。既存稼働P44は更新しない。
5. 非公開Draft Releaseに全入力・出力・SHAレシートを保存。immutable asset IDから独立再取得して全量SHA照合する。
6. 署名、新P25実機書込み、slot切替、再起動、無線送信は、個別承認と有限A試験の復旧計画が揃うまで別ゲート。GNSSはこの変更に含めない。

## 現時点の判定
- 公開レシピ履歴の確認：PASS
- 既知良好実機ペアの特定：PASS（過去の実測記録による）
- 成功版kernel build provenance全資産の取得：BLOCKED（この作業環境からraspi4の非公開ファイルシステムにアクセス不可）
- Wi-Fi変更前のImage再現：NOT_TESTED
- 新しいWi-Fi対応unsigned P25/P44製造・保存：NOT_DONE
- C号機への変更：NONE

参考：[PR #25](https://github.com/Karin-Laboratory/Debian13-Terminal6/pull/25)、[実機復元記録](https://github.com/Karin-Laboratory/Chappie-Memory/blob/main/terminal6/c-unit-kvm-p25-p44-restore-test-2026-11-19.md)、[段階移行記録](https://github.com/Karin-Laboratory/Chappie-Memory/blob/main/terminal6/C%E5%8F%B7%E6%A9%9F_KVM%E8%B5%B7%E5%8B%95%E6%88%90%E5%8A%9F%E7%89%88%E3%81%8B%E3%82%89%E8%A8%AD%E8%A8%88%E6%86%B2%E7%AB%A0v1.4%E3%81%B8%E3%81%AE%E6%AE%B5%E9%9A%8E%E7%A7%BB%E8%A1%8C_20261119.md)。
