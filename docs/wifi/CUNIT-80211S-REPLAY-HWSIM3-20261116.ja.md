# C号機802.11s: ソース再現と3ノード仮想試験の実行手順（2026-11-16）

## 判定

- 既存ARM64 Image/modulesと2ノードhwsim成功は記録済み。ただし**既存成果物のハッシュ一致は、ビルドの再現性を証明しない**。
- 標準Linux 6.18.63のtarにはMT6990 vendor sourceが足りない。既存private treeに相当する完全な差分・ライセンス確認済みのpatch seriesが必要。**現時点で完備していない**。
- このPRでソース再生ゲートと厳格な3ノード試験を追加したが、どちらもこの変更時点では**未実行・未合格**。実機試験も未実施。
- PR #9の[OTP/EEPROM修正](../../patches/0001-mt7996-eeprom-calfree-timeout.patch)を最後に適用する。PR #6の6GHz/P25領域は操作しない。

## 第1ゲート: private tree と独立再生源を一致させる

実行場所はソースとクロスコンパイラが存在する**所有者のprivate build host**に限定する。全patchは合法的に再頒布できるか個別に確認し、vendor blob・EEPROM・鍵・端末識別情報をGitHubへ持ち出さない。

1. 元のLinux 6.18.63 tarballのSHA256を検証する。記録値は `81764a545072d160748beff4d9de2e7d95aa9f16e8261110288f067a2cc61d71`。
2. 現行private treeとLinux stableの全**ソースファイル**を比較し、MT6990のclk/pinctrl/DTS/Kconfig/Makefile等を含む差分を独立したパッチ列として整理する。build outputを入力ソースとして扱わない。
3. 再配布権限が確認できたパッチを、必要な順に用意する。**最後はPR #9パッチ**。この差分がまだ揃わなければ再現性はBLOCKED。
4. `python3 -m scripts.replay_80211s_kernel_source` で、標準tarから一時ディレクトリへ展開、全パッチを順番に適用、private treeとのファイル単位SHA256を照合する。
5. 同じツールの `--build-artifacts` を指定した場合のみ、すべてのソースが一致した**別の隔離ディレクトリ**で `olddefconfig; Image modules` を実行。終了後、Imageとmt76関連AArch64 modulesをprivate領域に保存する。実機へは送らない。
6. config、コンパイラ、リンカ、パッチ列、ソースツリー、生成物のハッシュを所有者専用JSONに残す。ツールはvendor/privateファイル名を結果に含む可能性があるため、**JSONを公開しない**。公開するのは承認した非機密の照合結果と判定のみ。

引数例（`--patch` は**実在するすべてのvendor/board差分**に対して繰り返す。以下の<...>は未取得入力の指定欄であり、そのまま実行しても成功しない）：

```bash
python3 -m scripts.replay_80211s_kernel_source \
  --upstream-tar /home/masataka/private/debian13-proto3-build-20261112/source/linux-6.18.63.tar.xz \
  --upstream-sha256 81764a545072d160748beff4d9de2e7d95aa9f16e8261110288f067a2cc61d71 \
  --private-tree /home/masataka/private/cunit-80211s-build-20261115/kernel-src \
  --patch <first-approved-vendor-or-board.patch> \
  --patch <next-approved-vendor-or-board.patch> \
  --patch patches/0001-mt7996-eeprom-calfree-timeout.patch \
  --final-config /home/masataka/private/cunit-80211s-build-20261115/kernel-src/.config \
  --cc "$(command -v aarch64-linux-gnu-gcc)" \
  --ld "$(command -v aarch64-linux-gnu-ld)" \
  --build-artifacts /home/masataka/private/cunit-80211s-replayed-artifacts \
  --output /home/masataka/private/cunit-80211s-replay-report.json
```

`--build-artifacts`を省略したときはソース照合だけを実施する。**SOURCE_REPLAY_MATCH≠BUILD_PASS**。ビルド後は `CONFIG_MAC80211_MESH=y` と `CONFIG_MT7996E=m` を要求する。パッチが部分的しか存在しない場合、ツールは失敗として終了し、候補Imageは生成しない。

## 第1ゲート補助：元Git履歴が欠落したprivate sourceからpatchを再構成

[private差分の再構成ツール](../../scripts/reconstruct_80211s_vendor_patch.py)は、既存のGit履歴がないLinux build treeにも適用できる。標準Linux tarballと実ソースsnapshotを比較し、snapshotに含まれるPR #9のEEPROM/OTP差分を逆適用した状態をvendor/board変更として抽出する。次に `vendor patch → PR #9 patch` を完全に別の一時展開元に当て、全ソースのSHA256一致を検証する。これは**バイト列の再現性**であり、vendorコードの出所・再配布可能性や実機での動作を証明しない。

owner-privateホストでのみ以下のように実行する。

```bash
python3 -m scripts.reconstruct_80211s_vendor_patch \
  --upstream-tar /home/masataka/private/debian13-proto3-build-20261112/source/linux-6.18.63.tar.xz \
  --upstream-sha256 81764a545072d160748beff4d9de2e7d95aa9f16e8261110288f067a2cc61d71 \
  --private-tree /home/masataka/private/cunit-80211s-build-20261115/kernel-src \
  --pr9-patch patches/0001-mt7996-eeprom-calfree-timeout.patch \
  --private-output-dir /home/masataka/private/cunit-80211s-vendor-patches \
  --ack-private-only
```

出力される `PRIVATE-MT6990-vendor-board-source.patch` と `PRIVATE-MT6990-source-manifest.json` は0600で保存し、Git管理領域への保存を拒否する。**公開禁止・内容監査前の資料**であり、GitHubへpushしない。差分が再現できない場合はfail closed。旧[PR #1 のstable upgrade手順](https://github.com/Karin-Laboratory/Debian13-Terminal6/pull/1)は6.18.44→6.18.63の3-way mergeと個別解消を記録しているため、元ソースの履歴調査で併せて参照する。

合格後に前節の `--patch` へprivate vendor patchを指定し、PR #9パッチを最後に続ける。さらに独立ARM64ビルドとconfig・toolchain・成果物のハッシュを検証する。元vendorソースの権利根拠が不明ならpublic patchは作らず、**privateのみで再現可能な状態**と明記する。

## 第2ゲート: A-B-C の仮想無線で真の中継を検証

Linuxホストの隔離VM（既存の物理PHY・hwsim・wmediumdが存在しない環境）で、`iw`、`ip`、`ping`、`openssl`、`wpa_supplicant`、`wpa_cli`、`mac80211_hwsim`、`wmediumd`を用意して実行する。

```bash
sudo bash scripts/run_80211s_hwsim_3node.sh
```

- wmediumdはA↔B、B↔Cを損失率0%、A↔Cとその他すべてを100%にする。単なる3 PHY起動をもって中継成功とは呼ばない。
- 3ノードにランダムな共有SAEパスフレーズを設定して、各peerのESTAB状態とA-C直接peeringが無いことを照合する。
- A→C・C→A pingの後、AのHWMP pathの`destination=C, next_hop=B`と逆方向も検査する。
- B停止でA-Cが通信不能になること、B復帰でHWMPの次hopがBに戻ることを検査する。
- 20パケットの損失率とRTTを記録する。試験終了時には生成したnetwork namespace、hwsim、wmediumd、supplicantを片付ける。
- SAE設定と接続ログだけではフレーム暗号化を独立立証できないため、**AMPEの無線フレーム保護は別途capture/解析するまで未検証**と記録する。実機でのSAE/AMPEも未検証。

参考：[wmediumdの確率ベースリンク遮断](https://github.com/ramonfontes/wmediumd#per-link-loss-probability-model)。

## 第3段階: C号機へ統合する最小差分（準備のみ、実機未操作）

この節は **PR #6担当から実機引渡しがあった後**の手順書であり、今回のホスト試験を物理C号機の合格証拠に転用しない。

1. **ビルド入力**: 権利確認済みLinux 6.18.63 + private MT6990 vendor/board source + PR #9 EEPROM/OTP修正の順に再構成し、全ソースのSHA256一致、独立`Image modules`ビルド、toolchain/config/成果物SHA256をowner-private領域に保存する。現状、この実再構成はBLOCKED。
2. **kernel差分**: IEEE 802.11sに必要な追加変更は原則`CONFIG_MAC80211_MESH=y`のconfig fragmentと既存wpa_supplicantのmesh設定だけ。HWMP、SAE、AMPEの独自実装は作らない。`CONFIG_MT7996E=m`およびPR #9の校正修正が残ることを確認する。
3. **既存の起動・管理基盤**: eMMCの100MHz制限とCQE無効化、既存DTB・firmware、管理LAN/IPv4・SSH・UART・復旧用slot Bの構成を変更しない。ビルドconfig上の設定だけでなく、実機のdmesg/sysfsと通信で有効性を後日確認する。
4. **無線実機の順序**: 適法な2.4GHzまたは5GHzチャネルでmesh point capability → peer/SAE → 2ノードIP → 独立した3ノードHWMP → 障害復帰を逐次確認する。既存の管理用無線IFを勝手にdownしない。A号機は読み取り専用で、純正EasyMeshを802.11s peerと見なさない。
5. **役割分離**: PR #6のP25、署名、regdb・6GHz送信、MLO、EasyMeshに手を入れない。事前に引渡しとrollbackが確認できなければ物理C号機への適用を止める。320MHzおよび6GHz RF送信は対象外。

引渡し直後の非破壊ベースライン採取例（通信経路・MAC・個体識別情報を公開ログに貼らない）:

`uname -r; ip -br link; ip -4 route; iw phy; lsmod | grep -E 'mt7996|mt76|mac80211'; cat /proc/cmdline`

初回の実機試験で必要な最小変更、復帰操作、ログ採取範囲はPR #6担当との引継ぎ時に最終確定する。現時点で署名・書込み・RF実験は実施していない。

## 第3ゲート: 署名・C号機書込み前の受け入れ条件

ソース再生＋独立ビルド成功、PR #9の校正修正保持、eMMC 100MHz/CQE無効、最終configとfirmware整合性、管理LAN/SSH/UART保護、実機操作権の確保が必要。6GHz・MLO・EasyMesh担当の変更領域へ介入しない。PHYのmesh capability広告だけでは成功としない。

最初の実機2ノード試験は許可済みの2.4GHzまたは5GHzで、別途IEEE 802.11s対応peerを準備する。A号機の純正EasyMeshは802.11s peerとして扱わない。P25署名・書込みは6GHz担当の権限引渡し後でなければ行わない。
