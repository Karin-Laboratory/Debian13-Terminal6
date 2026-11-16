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

## 次のゲート

GitHub Actionsのstage4 `summary.json` から、最初の未成功工程とreturncodeを確定する。もし `start.sh` が失敗すれば、読み取り可能なkernel構成/モジュール、hostapd/wpa_supplicant、`iw dev` と名前空間環境を比較する。通常AP `ap_open` が通りMLDだけ失敗するなら、MLO特有のkernel/hostap互換性とlogを精査する。単なるtimeout延長はしない。

**この文書の作成自体は仮想通信成功の証拠ではない。CIの実行ID・完了結果を別途記録する。**
