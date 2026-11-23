# ① 4号機 Golden GSW / NETSYS限定修正版P25：署名完了記録（2026-11-23）

## 対象と承認範囲

所有者が**今回の未署名P25の正確なSHA-256だけ**を署名承認：

`23080614c990e56af7817dde9d666065543346bbcbf6a31bae1659cfd94e00fb`（33,554,432 bytes、32MiB）

- 用途：4号機Golden GSW版の**NETSYS子platformデバイス生成のみを検証する診断候補**。
- 修正内容はNETSYS親の `compatible` に `simple-bus`追加、`#address-cells=<2>`、`#size-cells=<2>` の3つのみ。既存の`ranges`、`/gsw@0`、他ノード、MAC、PHY、PCS等のプロパティは保持。
- 前回Golden P25の実機LK/Linux/UARTで起動したARM64 kernel gzipと内蔵initramfsは**バイト単位で同一**。boot-v2外部ramdisk 0維持。
- **重要：**既存`/gsw@0`の `mediatek,mt753x` は、固定ソースで検証済みの`mt7530-mmio` OF表に存在せず、直接bindを保証しない。NETSYSバス修正とGSWドライバ修復・LAN2通信成功は別の問題。

前回の4号機実機結果は[PR #46 G4 FAIL報告](https://github.com/Karin-Laboratory/Debian13-Terminal6/pull/46#issuecomment-7087588055)。純正Bへ復帰済み、C号機はDebian基準機として保管中。

## 署名済みP25正本

**署名済みP25 SHA-256：**

`2fc47ec23959faf7efee337e86bc2d3d777c7aca196614ed2b375a36e0214493`

- サイズ：**33,554,432 bytes**
- 署名対象unsigned P25 SHA：`23080614c990e56af7817dde9d666065543346bbcbf6a31bae1659cfd94e00fb`
- 変更後DTB table SHA：`8db9b043b2ca73b92464edc7a9c456367a34ae34a3ba61a8dcb5bdda5416b6be`
- 前回Golden unsigned P25 SHA：`fb49c4e8c3921b58d7232b309620ce876a5c624868b129fc74d25a7f641595ac`
- 既知実績ARM64 Image SHA：`5b93f5aa976968796396612f8107ebf0f1be173dc587465527d1653c3b2dcfb8`
- 組込みinitramfs gzip SHA：`ff14bbfbb2ab376b95235a0ed9e57db8bc6435147c49492a654ada9aa459aa9a`

### 所有者非公開成果物

- 非公開製造CI：[Actions #45085981233](https://github.com/Karin-Laboratory/SBAT6A-Offline-Archive/actions/runs/45085981233)：**SUCCESS**（2回組立、独立FDT全プロパティ確認、全量読戻し）。
- 保護署名CI：[Actions #45086900742](https://github.com/Karin-Laboratory/SBAT6A-Offline-Archive/actions/runs/45086900742)：**preflight / sign-onceともにSUCCESS**。
- 非公開Draft Release ID：**`454849331`**。
- 署名済みP25 asset ID：**`780909388`**、ファイル名 `C4-GSW-NETSYS-23080614-SIGNED-UNTESTED-p25.img`、SHA `2fc47ec23959faf7efee337e86bc2d3d777c7aca196614ed2b375a36e0214493`。
- 独立暗号検証レシート asset ID：**`780909713`**、1708B、SHA `e6df26f039b2bf10ffb699eb1df6946b43f554dd8e8d3a03af80ad44a2d4deab`。
- 非公開署名コードと承認ゲート：[Draft PR #200](https://github.com/Karin-Laboratory/SBAT6A-Offline-Archive/pull/200)、元unsignedとNETSYS診断コード：[Draft PR #199](https://github.com/Karin-Laboratory/SBAT6A-Offline-Archive/pull/199)。

### 実際に通過した署名受入

1. 指定unsigned SHA、正確なサイズ、ビルドレシートSHA、既知成功Imageと内蔵loader、Golden基準FDTとの独立差分検証：PASS。
2. 前回成功した固定署名ヘルパー3コミットとself-hosted保護署名ランナー、排他lock、承認SHA固有のone-shot markerで一度だけ署名：PASS。
3. 別プロセスによるROOT／IMAGE証明書RSA-PSS検証、signed bodyのunsignedとの完全バイト一致、boot-v2 signed header確認：PASS。
4. 32MiB成果物全量SHA、非公開Draft Releaseへのアップロード、asset ID指定での再ダウンロードと`cmp`、SHA確認：PASS。
5. 新候補の**実機LK/Linux/UART/eMMC/LAN2/SSH/kexec：すべてNOT_TESTED**。

**最終判定：`EXACT_SHA_SIGNED_RSA_PSS_AND_PRIVATE_READBACK_PASS`。G4修復完成ではなく、Golden GSW legacy driver bindは未解決。**

## 実機操作

今回の署名作業では4号機・C号機へ一切接続・操作しなかった。P25書込み・slot変更・再起動、P26/P43/P44、純正slot B、GPT/LK、モデム/NV/校正領域変更は実施していない。

将来の4号機のみの有限slot A試験で、まずG1〜G3の回帰、次にNETSYS子platform device登録、Ethernet MAC probe、legacy GSWドライバbind可否、DSA/lan2、ARP/双方向ICMPを順序立てて測定する。最初のFAILで後続へ進まずstock Bへ復帰する。C号機基準機を操作しない。**今回の署名承認を新たな実機試験承認と解釈しない。**
