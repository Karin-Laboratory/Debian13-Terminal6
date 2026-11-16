# C号機 MLO 第4段階：GitHub Actionsでのhwsim実通信再現

2026-11-16 JST。対象：[統合Draft PR #13](https://github.com/Karin-Laboratory/Debian13-Terminal6/pull/13) をbaseとする [MLO専用Draft PR #16](https://github.com/Karin-Laboratory/Debian13-Terminal6/pull/16)。PR #13 / main / PR #6 / PR #10 のブランチは変更しない。

## 前回の実測と本段階の仮説

- 開発VMは Debian 13、Linux `6.12.101+deb13-amd64` で上流hostapの3 smokeがPASS、別の仮想5/6GHz 160MHz fixtureで双方向IP ping 6/6。これは過去の記録であり、今回の再計測ではない。
- GitHubの [Azure実行 #43804859049](https://github.com/Karin-Laboratory/Debian13-Terminal6/actions/runs/43804859049) は `7.0.0-1017-azure`、[AWS実行 #43805577351](https://github.com/Karin-Laboratory/Debian13-Terminal6/actions/runs/43805577351) は `7.0.0-1014-aws`。双方とも `mac80211_hwsim` の `mlo/multi_radio/channels` が利用可能な状態で、最初の `eht_mld_owe_two_links` が250秒で未完了、接続イベント0。接続未成功でありkernel起因とはまだ断定できない。
- 以前のrunnerは `timeout 240s run-all.sh ...` 全体しか監視せず、startup・test本体・stopのどれが停止したか判定できなかった。

## 変更と検証手順

上流hostapの **`start.sh channels=2` → `run-tests.py` → `stop.sh`** を別個に起動・診断する。上流のEHT MLDプロトコルやテストを置き換えない。開始前に物理Wi-Fi PHYなし、権限、hwsim MLO/multi_radioサポートを検査。専用の破棄可能なGitHub-hosted VMだけで実行する。

`scripts/cunit_mlo_hwsim_stage4.py` の工程は次の通り。

1. hwsim構築 `start.sh channels=2`（90秒上限）。
2. 通常AP/STA経路の `ap_open`（65秒上限）。ここで失敗すれば、MLD特有の問題とは決めつけず次を停止。
3. `eht_mld_owe_two_links`、`eht_mld_link_removal`、`eht_mld_disassociate` を各100秒上限で独立起動。最初の失敗で次を止める。
4. `stop.sh` を成功・失敗とも `finally` で実施（25秒上限）。
5. 3件成功した場合のみ既存の仮想 `cunit_mlo_5g160_6g160` を別ジョブ工程で実行し、単一MLD・2リンクと双方向IPの証拠を確認。

各工程で `start/finish`、実行秒数、returncode、timeout、PASS/FAIL/associationイベントの**件数だけ**を標準出力と `summary.json` に書く。上流の生ログ、MAC、SSID、IP、内部設定はprivate outputに限定し、GitHubへアップロードしない。タイムアウト時は独立プロセスグループにTERM、必要ならKILLで確実に停止を試みる。後処理の失敗も成功判定から除外する。

単体テスト（合成シェルfixture）は本物の無線通信証拠ではない。Actionsの`workflow_dispatch`またはbranch pushで、実buildしたhostapとLinux hwsimに対してのみ、上記の実通信試験を実行する。

## 再現コマンド（専用VM）

```sh
python3 -m compileall -q scripts tests
python3 -m unittest tests.test_cunit_mlo_hwsim_runner tests.test_cunit_mlo_stage4 -v

# 既存CI通り: hostap f1e9b5086718ad567dc40e3d5a1456534d51749f
# 固定ソース・既存patch・upstream build.shを実施後:
sudo python3 scripts/cunit_mlo_hwsim_runner.py probe --hostap-tree /tmp/cunit-hostap
sudo env CUNIT_MLO_ISOLATED_VM=YES python3 scripts/cunit_mlo_hwsim_stage4.py \
  --hostap-tree /tmp/cunit-hostap \
  --output-dir /tmp/cunit-hwsim-smoke \
  --tests eht_mld_owe_two_links eht_mld_link_removal eht_mld_disassociate
# 上3件が成功した場合だけ:
sudo env CUNIT_MLO_ISOLATED_VM=YES python3 scripts/cunit_mlo_hwsim_stage4.py \
  --hostap-tree /tmp/cunit-hostap \
  --output-dir /tmp/cunit-hwsim-wide --sim-country CA \
  --tests cunit_mlo_5g160_6g160
```

`--sim-country CA` は**完全な仮想Wi-Fi環境のみに許容**し、C号機に転用しない。320MHz送信、C号機/A号機/raspi4の変更はいっさい行わない。

## PASSの境界

- 回帰テストPASS：Python/監視器の動作のみ。
- upstream hwsim smoke3件PASS：仮想MLDの上流試験受入まで。リンク別IP・カウンタの証拠がなければ `HWSIM_PASS` ではない。
- 5/6GHz 160MHzの仮想MLD、双方向IP PASS：当該仮想試験の到達点。周波数幅・リンク別TX/RXと切断・復帰の証拠は別。
- [Acceptance v2](CUNIT-MLO-EVIDENCE-V2-20261116.ja.md) に必要な異なるradio ID、AP/STA同一MLD、リンク別カウンタ、双方各リンクdown/up、reconnect、全段階IP継続が実際に揃った場合だけ `HWSIM_PASS` を検討。C号機RF通信のPASSは別扱い。

## 最初のGitHub runner実測（2026-11-16）

[Stage4 CI #43807784250](https://github.com/Karin-Laboratory/Debian13-Terminal6/actions/runs/43807784250) はkernel `7.0.0-1014-aws` 上で、上流 `start.sh channels=2` が **10.00秒、終了コード1** で失敗した。独立後処理の `stop.sh` は **1.42秒、終了コード0**。従って `ap_open` とMLO 3件は **NOT RUN**。上流buildとPython 26件はPASS。これにより「250秒timeoutで関連付けイベント0」の直前に、hwsim環境準備失敗が存在することを切り出せた。前回の250秒全体timeoutが、起動した子プロセスによるstdout pipeの継承に関連する可能性はあるが、まだ仮説とする。

同じ実行のJSON artifactは、Pythonがroot/0700 directoryで保存したデータを非rootのupload actionへ直接渡し、`EACCES` となった。このため、rootが特定の **sanitized JSONだけ** をrunnerの可読ディレクトリへコピーしてからアップロードする修正を追加。生ログは引き続きprivate保管。以後のrunで新しいartifactの保存結果と `start.sh` の失敗分類（WPAソケット/hostapd/カーネル/権限など）を照合する。

[run #43808048460](https://github.com/Karin-Laboratory/Debian13-Terminal6/actions/runs/43808048460) はさらに `hwsim_module_loaded=true`、`phy_count=7`、`netdev_count=7`、`hostapd_processes=2`、`wpa_supplicant_processes=3` を確認。初期化が全く始まらないのではなく、仮想PHY生成後に停止したことを示す。[run #43808212246](https://github.com/Karin-Laboratory/Debian13-Terminal6/actions/runs/43808212246) は `wpa_control_socket` の接続失敗を分類し、サニタイズ済みartifactの保存も成功した。**初期化失敗原因の最終確定ではなく、個別ソケットの疎通確認へ進む。**

[run #43808342853](https://github.com/Karin-Laboratory/Debian13-Terminal6/actions/runs/43808342853) では、`wpa_supplicant` 制御ソケットの実応答を追跡。wlan0側はsocket不在/PONG失敗、wlan1とwlan2はPONG成功。global追加ソケットのうち5はPONG成功、6/7は不在。hostapdのglobal socketは存在。よって1個のhwsim radioが無いのではなく、wlan0だけで適用される起動オプションの違いも疑われる。

上流 `start.sh` のwlan0専用経路でオプション `-u`（D-Bus登録）が付く構造が確認されているため、専用VM内に限定してその**任意のD-Bus登録だけ**を除外する比較試験を追加した。対象hostap commit `f1e9b5086718ad567dc40e3d5a1456534d51749f` と想定ソース行に一致しない場合は安全側で停止する。これはまだ仮説検証であり、C号機のD-BusやWi-Fi管理には一切適用しない。

### 最新到達点の判定

- 診断器単体のホストCIはPASS。
- GitHub MLO実通信smoke3件は **NOT RUN**。
- 同一MLD・2リンク、リンク別TX/RX、リンク断復旧、仮想双方向IPは **NOT PROVEN**。
- 追加のstage4 CI実行は独立PR #16で進行。成功を確認していない項目を事実に昇格させない。

## 次のゲート

GitHub Actionsのstage4 `summary.json` から、最初の未成功工程とreturncodeを確定する。もし `start.sh` が失敗すれば、読み取り可能なkernel構成/モジュール、hostapd/wpa_supplicant、`iw dev` と名前空間環境を比較する。通常AP `ap_open` が通りMLDだけ失敗するなら、MLO特有のkernel/hostap互換性とlogを精査する。単なるtimeout延長はしない。

**この文書の作成自体は仮想通信成功の証拠ではない。CIの実行ID・完了結果を別途記録する。**
