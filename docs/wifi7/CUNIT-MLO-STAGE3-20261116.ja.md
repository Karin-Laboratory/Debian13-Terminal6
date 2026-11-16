# C号機 MLO 第3段階：上流MLD試験・仮想IP通信（2026-11-16）

## 位置づけと引継ぎ

- 対象は [PR #10](https://github.com/Karin-Laboratory/Debian13-Terminal6/pull/10) の `codex/cunit-mlo-radio-map-20261115` のみ。
- 上流 hostap は ChromiumOS mirror の `f1e9b5086718ad567dc40e3d5a1456534d51749f` に固定。[`tests/hwsim/test_eht.py`](https://chromium.googlesource.com/chromiumos/third_party/hostap/+/f1e9b5086718ad567dc40e3d5a1456534d51749f/tests/hwsim/test_eht.py) の EHT MLD と `hwsim_utils.test_connectivity()` を再利用する。上流テストのライセンス表示は BSD。上流コードを独自フレームワークへ書き直さない。
- Linux の `mac80211_hwsim`、`ipvlan`、名前空間、hostapd / wpa_supplicant を利用。実機用MT7990の独自MLDプロトコルは追加していない。
- PR #6 のP25/regdb/署名処理、PR #9 の校正・EEPROM、他のEasyMesh/802.11sブランチは変更しない。

## 今回の変更

- [ランナー](../../scripts/cunit_mlo_hwsim_runner.py)：上流 `run-all.sh --channels 2 TEST` 形式を使用し、1件240秒の上限と最初の失敗テスト名を匿名要約へ保存。最初に失敗したら打ち切り、見かけのCI成功を排除。
- [5/6GHz仮想フィクスチャ](../../scripts/hwsim/test_cunit_mlo.py)：従来の5GHz ch36 / center50 と6GHz ch5 / op_class134 / center15の各160MHz、OWEによる単一MLDの関連付けと上流のL2 traffic_testに続け、実際のIPv4パケットを試行する。
- 実IPはAP/STA双方の親無線インターフェースを動かさず、それぞれ独立したネットワーク名前空間に `ipvlan l2` 上位インターフェースを設ける方式。仮想用 `198.18.0.1/30` と `198.18.0.2/30` を割当て、双方から6回ずつpingして実受信数を取得。親にIPを割り当てないことでローカル配送による偽陽性を避ける。
- pingの応答が確認できない場合は例外でテスト失敗。標準出力に正規化された `CUNIT_MLO_IP_BIDIRECTIONAL_PASS` が観測された場合だけ送信/受信数を要約へ転記する。欠落・不整合は推定で補完しない。
- 匿名要約ラベルを `UPSTREAM_MLD_SMOKE_PASS`、`WIDE_MLD_SMOKE_PASS`、`WIDE_MLD_IP_PASS` に分離。ただしどの場合も `acceptance_v2=NOT_PROVEN` のまま。
- [CI](../../.github/workflows/cunit-mlo-hwsim.yml)：隔離されたGitHub-hosted Linux VMに `iputils-ping` を追加。物理Wi-Fiの有無と権限・hwsim機能の事前確認を維持。生ログはVM内のみ、GitHubへは匿名要約だけをアップロード。
- [回帰テスト](../../tests/test_cunit_mlo_hwsim_runner.py)：チャンネル指定、ワイド試験のラベル、最初の失敗、ping成功行のパース、不正なパケット数の棄却を追加。

## CIと実測の境界

- 初期 [run #43785577376](https://github.com/Karin-Laboratory/Debian13-Terminal6/actions/runs/43785577376) について、2026-11-16 10:35 JST頃の取得では **実行中**。Python回帰、VM依存、hwsim事前確認、上流hostapビルドは成功し、上流MLD試験の実行ステップに進んでいた。**完了・通信成功の証拠は未取得**。
- 追加中の [run #43786961049](https://github.com/Karin-Laboratory/Debian13-Terminal6/actions/runs/43786961049) は、ping成功行を検査するPython回帰テスト1件の改行表記ミスで失敗。無線・IP通信の失敗ではない。続く `94dd61a8` でテスト修正。
- [最新の修正版run #43786976450](https://github.com/Karin-Laboratory/Debian13-Terminal6/actions/runs/43786976450) は同時点でビルド中。MLD関連付けと双方向IP、障害復旧の実測成否は未確定。GitHub Actionsの最終結果と各ステップ、可能なら匿名artifactを再取得して記録する。
- ローカルの現実行環境ではhwsimモジュールとCAP_NET_ADMINが不足し、Linux VMの無線実行は再現できない。GitHub-hosted Linux VMの独立試験結果を使用する。

## 未達項目と必要な証拠

1. 上流テスト3件のPASS / FAIL、最初の失敗箇所の確定。各個別テストの結果は **runの実ログ** に基づく。
2. 専用5/6GHz 160MHzで同一MLDの2リンクactiveと双方向pingが成立すること。設定値だけでは実際の周波数・幅を証明しない。
3. AP/STA双方のMLD状態、リンク別の実際のradio ID、TX/RX前後カウンタ、両リンクそれぞれの停止/復帰、再関連付け。**現フィクスチャの `n_channels=2` は異なるradio IDの証明ではない。**
4. 各段階の継続IP、RTT・損失率・可能な場合のiperf3、[受入schema v2](CUNIT-MLO-EVIDENCE-V2-20261116.ja.md)に結びついた匿名観測原本。
5. PR #6担当の引渡し後にC号機固有radio topology / regdb / ドライバを照合。6GHz RFは個体認証と国内運用条件の成立まで禁止。A号機は読み取り専用で比較。

**上流のL2フレーム通信、ワイドフィクスチャの関連付け、名前空間間IP、最終v2のHWSIM_PASS、C号機実機PASSは別の成果として管理する。現時点で最終2件を主張しない。**
