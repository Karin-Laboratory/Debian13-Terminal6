# C号機 MLO 第2段階：host実通信ハーネス（2026-11-16）

## 実装

- [専用hwsimランナー](../../scripts/cunit_mlo_hwsim_runner.py)：MLO/multi_radioモジュール、CAP_NET_ADMIN、物理Wi-Fiの不在、上流テストの存在を検査。独立VMと明示した環境でのみ実行。
- [5/6GHzの160MHz試験](../../scripts/hwsim/test_cunit_mlo.py)：hostap EHTヘルパーで2リンクMLD、wpa_supplicant関連付け、双方のリンクへのトラフィックを試みる。5GHz ch36/center50、6GHz ch5/op_class134/center15を合成設定。320MHzは禁止。
- [host回帰テスト](../../tests/test_cunit_mlo_hwsim_runner.py)：PASS行と終了コード、SKIP/FAIL混入、物理PHY検知を検証。
- [Linux VM CI](../../.github/workflows/cunit-mlo-hwsim.yml)：GitHub-hosted Linux VMで上流MLD試験の実行を試みる。生ログは公開せず、結果要約のみを保存。

## 環境と実測

上流ソースは ChromiumOS hostap のコミット f1e9b5086718ad567dc40e3d5a1456534d51749f に固定。上流 tests/hwsim/build.sh のビルドと run-all.sh の試験を実際に実行する。上流 `eht_mld_owe_two_links`、`eht_mld_link_removal`、`eht_mld_disassociate`を選択し、5/6GHz試験は別の実験的test_cunit_mlo.pyとして追加する。この版はARM64 hostapd 2.12の実機互換を保証しない。

現実行コンテナはDebian 13、Linux 6.18.57。modinfo mac80211_hwsimはModule not found、ネットワーク名前空間作成はOperation not permitted、iw/hostapd/wpa_supplicantは見つからなかった。Python構文検査とランナー13件の単体テストのみ成功。**MLO関連付け、リンク別通信、障害復帰は未実施であり、HWSIM_PASSではない。**

## VM実行

実運用ネットワークで実行しない。物理Wi-Fiが一切存在しない破棄可能VMで、上流リポジトリを上記コミットへcheckout・build後、次の順で実行する。

1. `sudo python3 scripts/cunit_mlo_hwsim_runner.py probe --hostap-tree /tmp/cunit-hostap`
2. `sudo env CUNIT_MLO_ISOLATED_VM=YES python3 scripts/cunit_mlo_hwsim_runner.py run --hostap-tree /tmp/cunit-hostap --tests eht_mld_owe_two_links eht_mld_link_removal`
3. `sudo env CUNIT_MLO_ISOLATED_VM=YES python3 scripts/cunit_mlo_hwsim_runner.py run --hostap-tree /tmp/cunit-hostap --tests cunit_mlo_5g160_6g160`

国コードを一時適用する`--sim-country CA`は合成無線だけのVMに限る。C号機へ転用しない。実行後の要約はupstream MLD smokeの成否だけで、`acceptance_v2`を必ず`NOT_PROVEN`にする。

## 未実装・C号機統合境界

[MLO受入判定v2](CUNIT-MLO-EVIDENCE-V2-20261116.ja.md)のHWSIM_PASSには、別radio IDの真正な取得、2リンク160MHzの実動作、各リンクTX/RXの増加、両リンクの障害・復帰、再接続、AP/STAの同一MLDを実ログから取得する必要がある。今回のランナーはそれらを合成しない。個人のMAC/SSID/秘密や生パケットログを公開リポジトリへ保存しない。

[PR #6](https://github.com/Karin-Laboratory/Debian13-Terminal6/pull/6)のP25・regdbや[PR #9](https://github.com/Karin-Laboratory/Debian13-Terminal6/pull/9)の校正は変更しない。C号機は6GHz担当の引渡し後まで無操作。A号機は読み取り専用。復帰時はeMMC 100MHz/CQE無効、管理LAN/SSH/UARTを維持。国内6GHzの認証・規制条件が確定するまでRF送信しない。

参考：[上流hostap EHT MLD試験](https://chromium.googlesource.com/chromiumos/third_party/hostap/+/f1e9b5086718ad567dc40e3d5a1456534d51749f/tests/hwsim/test_eht.py)。

## 通信の意味と受入境界（追補）

上流 `tests/hwsim/test_eht.py` の `traffic_test()` は `hwsim_utils.test_connectivity()` による**データフレーム送受信テスト**であり、`ping`、IPv4/IPv6、名前空間で隔離した双方向IP通信、スループットの代用にはならない。上流の2リンクOWEやlink removalテストは主に2.4GHzの仮想通信であり、5GHz 160MHz＋6GHz 160MHzの達成ではない。専用の`test_cunit_mlo.py`もAP/STAの関連付けとデータフレーム通信を試みる段階であり、リンク別実カウンタの読取り、片リンク停止後の双方向IPと復帰・再接続のv2証拠収集をまだ実装していない。従って上流テストのPASSやこのCIの緑表示を`HWSIM_PASS`と報告しない。

次の独立VM工程では、各無線リンクを同一MLDとして識別したうえで、IPのローカル配送を避けるため両端に別々のネットワーク名前空間を用意し、hostapd/wpa_supplicantのインターフェース操作の互換性を確認する。明示的なリンク別netlink/debugfsカウンタ・頻度・帯域幅を取れない場合は`NOT_PROVEN`のままとする。C号機への適用はPR #6担当の引渡し後のみ。
