# C号機 MLO受入判定 v2（host側・2026-11-16）

## 実装範囲と限界

`scripts/cunit_mlo_acceptance.py` はJSONで提供された**観測記録の整合性**だけをオフライン判定する。ネットワーク接続、C号機の変更、RF送信、署名操作は行わない。入力の真実性を機械的に証明する仕組みではないので、実機の生ログ、測定者、機器個体と測定時刻との紐付けは非公開の原本側で別途監査する。公開リポジトリには実MAC、SSID、PSK、個体固有EEPROM/OTP、秘密ログを置かない。

従来版は、数個の真偽値と合成カウンタだけで `PASS` を返し、同一MLDの両端状態やリンク断・復帰が欠落していた。v2では `schema_version: 2` が必須で、旧形式は `NOT_PROVEN` にする。これにより以前の受入入力は移行が必要になる。

## 証拠の契約

必須項目（以下は説明用のフィールド名で、実機値の例ではない）。

- `environment` は `hardware` または `hwsim`。`hardware` のみ別途確定した `six_ghz_authorization_verified: true` が必須。`hwsim` に国内RF送信許可のゲートを適用しない。
- `same_mld_peer: true`、`sta_mlo_capable: true`、`ip_bidirectional_pass: true`。単独のinterface接続やEHT能力広告の代用を認めない。
- `ap_mld` と `sta_mld` はいずれも `associated: true`、同じ**匿名の** `association_tag` と、同じ2つの `active_link_ids` を持つ。`association_tag` は生のMACアドレスを使わず、観測セッションのローカル識別子とする。
- `links` は2件ちょうど。異なる `link_id`（0〜15）と `radio_id` を持ち、bandは5GHz/6GHzが1件ずつ、widthは各160MHz。各linkに `active: true`、`associated: true`、 `primary_freq_mhz`、`center_freq_mhz`、 `tx_before/tx_after`、 `rx_before/rx_after` が必要。カウンタは各リンクで送受信とも増加する。radio IDは`iw phy`のper-radio inventoryとドライバの対応で特定し、PCI 7990/7991やwiphy番号から推定しない。
- `transitions` は5件。各リンクを一度ずつ `link_down` → `link_up` の順に試し、停止中は他方だけがactive、復帰後は両方activeに戻る。最後に `reconnect` を行い、各段階で `ip_bidirectional_pass: true` と正しい `active_link_ids` を記録する。片側の停止・復帰順は任意だが、2つの復旧サイクルの重複や並列化は認めない。

320MHz、片リンクだけの増分、radio ID重複、AP/STAのMLD識別不一致、中心周波数の矛盾、復旧未確認、旧形式は不合格。周波数帯の静的整合性は**規制適合の証明ではない**。とくに5GHz/6GHzとも160MHz RF動作の可否は、署名済みregdbおよび当該C号機の技術基準適合・運用条件が成立した後に別途判断する。

## 判定ラベル

| `mlo_two_link_ip` | 意味 |
|---|---|
| `PASS` | `environment=hardware` と申告された証拠がv2契約を満たす。実機原本照合を省略できるわけではない |
| `HWSIM_PASS` | `environment=hwsim` と申告された証拠がv2契約を満たす。**C号機の実機合格ではない** |
| `NOT_PROVEN` | 証拠が不完全・矛盾または未提出。理由を `reasons` に出力 |

検査対象は受入証拠の形式と整合性であり、実際のMLO制御やkernel/firmwareの正常動作まで保証しない。単体テストで作る正常形レコードは架空の入力であり、**hwsim実接続試験の成功を意味しない**。

## オフライン再現

```sh
python3 -m compileall -q scripts tests
python3 -m unittest tests.test_cunit_mlo_acceptance -v
python3 scripts/cunit_mlo_acceptance.py /path/to/private-sanitized-observations.json
```

受入コマンドは `PASS` または `HWSIM_PASS` で終了コード0、それ以外で1。`hwsim`/実機とも、観測原本がない場合は試験未実施と明記する。

## 合成環境への次の段階

別ホストで `modinfo mac80211_hwsim` を読み、`mlo` / `multi_radio` の機能有無とカーネル・hostapd 2.12のEHT/MLD対応を確認する。上流の hwsim EHT試験を参考に、**2つの独立STA/AP接続ではなく単一MLD**を形成し、双方向IP/リンク停止復帰を記録した場合に限り `environment=hwsim` の入力を作る。既存ホストでの `modprobe` やネットワーク設定変更はこの変更に含めない。上流参照：[hostapd hwsim EHT試験](https://chromium.googlesource.com/chromiumos/third_party/hostap/+/f1e9b5086718ad567dc40e3d5a1456534d51749f/tests/hwsim/test_eht.py)、[Linux mac80211_hwsimのMLO/multi_radioパラメータ](https://kernel.googlesource.com/pub/scm/linux/kernel/git/torvalds/linux.git/+/26b77009ee74f6122a067a4f9926ff6e09fffb94/drivers/net/wireless/virtual/mac80211_hwsim_main.c)。

実機は6GHz担当から操作権の引渡しがあり、認証・regdb・radio inventory・対応STAが揃うまで停止。A号機は保存記録または読み取り専用比較のみに限定する。