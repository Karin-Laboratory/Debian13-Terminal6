# C号機 MLO host側実装・実機ゲート (2026-11-16)

## PR #6追従

PR #10の旧base `9ed289379b2e04832984a8545373d14c74acd19d` に、PR #6の最新HEAD `7a0fa27d1b33596b1de13d8fdb2fdbecf9c35c89` を通常mergeした。PR #6は変更していない。後者の6GHz認証監査によると、署名済みregdb候補は存在するが、C号機での適用と個体認証条件は未確認である。6GHz RFは保留し、320MHzは使用しない。

## 6.18.63ソースと実機の境界

ピン留めされた6.18.63ソースの `mt7996/init.c:419-463` では `has_2ghz`、`has_5ghz`、`has_6ghz` を持つ各phyから `radio_phy[]`、`radios[]`、`radio_freqs[]` を作り、`wiphy->n_radio` を増やす。`init.c:508` はMLOフラグを立てる。`mt7996/main.c:1300-1317` はstation MLDに限り `mt76_select_links()` で2以上のactive linkを選ぶ。AP側の実動作はこの処理だけからは証明できない。`mt76/mac80211.c:2093` の選択はusable linkのbandを参照する。PCI 7990/7991の個数や `phy0` の個数からradio数を推定しない。

hostapd 2.12の実ソースには `CONFIG_IEEE80211BE`、`mld_ap`、`mld_addr`、`eht_oper_chwidth` のパーサーがある。機能の存在はC号機でのMLD association、5/6GHz 160MHz同時動作、通信を証明しない。Cの実 `iw phy` Radios inventoryは未取得である。

## 実装した受入判定

`scripts/cunit_mlo_acceptance.py` は読み取り専用のJSON証拠を判定する。2つの相異なるlink IDが同一MLD peerに属し、MLO対応STA、5GHz/6GHz各160MHz、両リンクのTX/RX前後カウンタ増加、双方向IP、6GHz認証ゲートの全てを必要とする。独立した2 STAや能力広告のみをPASSにしない。入力の `six_ghz_authorization_verified` は、別途人間が認証証拠を確定した後にのみtrueにできる。ツール自体は認証を証明しない。

実行例: `python3 scripts/cunit_mlo_acceptance.py private-evidence.json`。実MAC、SSID、鍵、payloadをJSONに入れない。現在の実機証拠では入力を完成できず、判定は未実証である。

## 検証

`python3 -m unittest tests.test_cunit_mlo_acceptance tests.test_cunit_wifi_runtime_audit -v` は16件PASS。合成の正常系に加え、別STA、停止したRX、認証不足、重複link ID、320MHzを拒否した。これはhost側判定の試験であり、実機MLO PASSではない。

## 実機アクセスと次の地点

現VMから許可されたraspi2 `codex` 経路でC号機rootへstrict SSHを試みたが `Permission denied (publickey)`。端末に変更を加えていない。`iw phy` の現物、radio inventory、MLD接続、link別カウンタ、6GHz認証条件は未取得。次は正規のC管理資格情報が使える状態で、まずread-only `iw phy` とdriver/firmware情報を取得する。6GHz認証ゲートが成立するまで5GHzのみでhostapd/MLDの段階試験に留める。MLO対応STAも未確認であり、Intel AX201を受入端末としない。
