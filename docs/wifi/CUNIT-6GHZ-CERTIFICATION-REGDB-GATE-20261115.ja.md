# C号機 6GHz技適・regdbゲート (2026-11-15)

## 判定

**6GHz送信は未許可・未実施。** 技適データベースにAirターミナル6の製品型式に一致すると考えられるA775の6GHz認証記録が見つかった。一方、C号機の底面銘板にある認証番号・型式の現物照合、認証時と改造後の無線構成一致、規制DB候補の署名と実機起動はこの作業セッションでは未確認。認証記録だけから改造後の送信が認証範囲内とは断定しない。

## 技適記録の照合

総務省の技適検索入口は[電波利用ホームページ「技術基準適合証明等を受けた機器の検索」](https://www.tele.soumu.go.jp/j/sys/equ/tech/)。

総務省公表データの検索結果を収録する[020-240075 / A775 詳細](https://fccid.io/giteki/020-240075)では、申請者 DASAN Networks, Inc.、型式 A775、登録証明機関 TAC、登録証明機関による工事設計認証として記録されている。6GHz設備の記録は電波法施行規則第2条第80号、中心周波数範囲5.955–6.415GHz。記載されたチャネル幅は20/40/80/160MHzで、**320MHzは記載されていない**。認証データの2025-10-24時点でも、この6GHz記録の幅・周波数の記載は同じである。元データの日本語欄と番号は同データベース上で確認した。個体の銘板番号が020-240075であることは未確認なので、C号機の表示を撮影または読取り、同一性を最後に確定する必要がある。

この記録は、A775について日本の6GHz無線設備としての認証があることを示すが、任意のOS/firmware、任意の出力・アンテナ・チャネル幅で送信可能という包括許可ではない。特にstock OSで設定表示された320MHzは、実送信や法令適合の証拠ではなく、製品別認証記録の幅にも含まれない。C号機の改造構成では320MHzを使用しない条件が必要。

## 国内6GHz運用条件

- [電波法施行規則（e-Gov）](https://laws.e-gov.go.jp/document?lawid=325M50080000014_20260401_508M60000008002)第6条第4項第4号(4)は、5925MHz超–6425MHz以下を、総務大臣が別途告示する条件に適合する小電力データ通信システムとして規定している。
- 総務省の[無線LAN屋外利用・上空利用案内](https://www.tele.soumu.go.jp/j/sys/others/wlan_outdoor/index.htm)では、6GHz帯の屋外利用はVLPに限られる。屋内用LPIを屋外・上空利用してはならない。
- [ARIB STD-T71の公式改定概要](https://www.arib.or.jp/kikaku/kikaku_tushin/desc/std-t71.html)は、6GHzを5925–6425MHzとし、7.0版で最大160MHz幅を定め、8.0版でIEEE 802.11be (Wi-Fi 7) 対応を反映したとする。これは当該A775の個別認証記録を320MHzへ拡張しない。
- 2022年導入時の総務省答申説明では、LPIは屋内、VLPは屋内外の別クラスである。C号機がどちらの認証構成・出力制御であるかは、銘板・製造資料と上記認証添付資料を突き合わせるまで未確定とする。

よって、本件の候補P25を適用して規制DBが読めても、それだけで6GHzの送信許可は成立しない。regdbは周波数・チャネル制限をカーネルへ提供するもので、個体認証・アンテナ利得・送信電力制御の証明に代わらない。

## P25候補と署名・復旧状況

候補はPR #6のregdb組込みビルド資産を対象とする。作業領域の現物SHA-256を再計算した。

| 成果物 | SHA-256 | 状態 |
|---|---|---|
| Debian signed regulatory.db | `2fb33ca0074db573e05ef7dd50bb45b63c0ff98b7e852e1105ebad536fae8e6b` | 候補initramfsに組込み |
| regulatory.db.p7s | `7417102f349fc43bb96197cf77a854b42d6f7702076064a3c83ef34cc42c5a6d` | 過去のビルド記録上OpenSSL detached signature verification PASS |
| regdb入りinitramfs CPIO gzip | `9e149a1e7deb3ff859f494bda801335f463962bc16349988f0046459298d55ca` | 候補素材 |
| Linux Image.gz | `a9c230d06ca2bbd99f4d8bda708dfcd7788b60eaef29f206f465910d6f256f45` | 同じbuild-treeの候補素材 |
| 初期 unsigned 32MiB P25 | `9686d1b27276c62ad4308d926c2a3667b19b58bac3dc5100686e00aef691a1e9` | **不採用**。再検査でMMC DTに`max-frequency=200000000`と`supports-cqe`が残存。C号機の100MHz/no-CQE基準を損なうため署名・適用していない |
| 安全化 unsigned 32MiB P25 | `f3cf2327287a1c388faa3e8b59cc09bf92bab08cb006cc84912ab2c32b370889` | initramfs/Image.gzを維持し、安全確認済み100MHz/no-CQE DTBのみを組み込み直した候補。P25構造検証PASS |
| signed 32MiB P25 | `8457ae5b31d38a754442ed0826544e19cf262059d8578b1eb0218d1cc3f2beb8` | 2026-11-15 protected signer workflow成功、独立RSA-PSS検証receipt PASS。非公開SBAT6A-Offline-Archive draft releaseに保管。実機適用・起動は未実施 |

カーネル設定は署名済みregdb必須であり、regdbと署名ファイルは早期initramfsに格納される。候補SHAに対する署名は、ユーザーが明示承認した後、保護された署名環境で実行した。workflow run [43676185512](https://github.com/Karin-Laboratory/SBAT6A-Offline-Archive/actions/runs/43676185512) はsuccess。receiptではunsigned SHAとの一致、署名body不変、RSA-PSS検証、証明書鎖検証を記録し、`device_action=NONE`・`physical_boot=NOT_TESTED`である。

また、2026-11-14に同一C号機で純正`quec_bootctrl -F`によるslot B起動と`quec_bootctrl -s`によるslot A復帰、各起動後SSH接続に成功した記録を復旧根拠として採用する。今回のユーザーは既存経路に加えて電源サイクル介入を復旧条件として承認した。今回signed P25のboot_a書込み、全量readback、実機起動はまだ未実施である。

次に必要な作業はsigned SHA・対象パーティションを再照合してからのC号機適用、全量readback照合、slot A復帰、起動後の早期kernel logでsigned regdb読込み確認である。署名成功だけでは実効regulatory設定や送信許可を意味しない。C号機の銘板/認証設計との一致と改造後の運用条件は依然未確認なので、6GHz RF送信は引き続き行わない。

## 実機観測との区別

PR #6/ #9にある最後のC号機測定では、Linux 6.18.63、global regulatory code `00`、6GHz advertised channels disabled、6GHz passive scanがInvalid argumentで失敗している。6GHz送信・認証・PSK検証はいずれも行っていない。これはPR記録の既測定結果であり、今回の作業セッション内での新規実機測定ではない。

この作業セッションではC号機、raspi4、UARTへ接続していない。署名成果物はホストへ取得し、P25のSHA-256とreceiptのunsigned/signed SHA、サイズ、DTBハッシュを照合した。実機への書込み・起動、regdbの起動時読込み、実効ルール/チャネル状態は未検証。

## 次の安全な検証

1. C号機の底面銘板の型式・技適番号をprivate evidenceで照合。
2. A775 / 020-240075の日本語認証原本・添付された設計/試験資料で、LPI/VLP区分、許容出力、アンテナ条件を確認。改造後構成との一致を専門的に確認する。
3. 上記不足物を解消して正規署名し、既知のstock slot recoveryを維持できると確認した後にのみ候補を起動する。
4. まずregdb署名読込、global/local regulatory、全チャネルdisabled flagsをread-onlyで確認。6GHz送信は別ゲートとして維持。
5. 認証資料が改造後構成のチャネル幅・周波数・電力条件を保証できない限り、6GHz RF試験を行わない。少なくとも現時点では320MHzを無効とする。  

## 2026-11-16 実機適用準備の再開

raspi4 (`192.168.0.38`) からC号機の既存SSH経路を再確認した。slot A/Debian 13の起動時点でboot_aの全量SHA-256は既知の100MHz/no-CQE P25 `dd9238441761e5896d78bf9553d2d5731ed04bcc6d603bf70a064ba620beabeb` と一致。MMC debugfsはHS400、8-bit、1.8V、actual 94,999,965Hz、`cmdq_en=0`。misc全体はraspi4の既存private backupと一致した。署名済みregdb候補もraspi4へ転送し、32MiBとSHA-256を照合した。

既存の純正経路どおり、rootfs Bをread-onlyでマウントしたchrootから純正`quec_bootctrl -F`を実行し、misc readback `0e000100000f00010000` を確認した。その後の再起動ではC号機IPがpingに応答する一方、SSH/HTTPはConnection refusedとなり、raspi4 UARTの読み取りキャプチャも空だった。slot BのOS起動をSSH/UARTで確認できていないため、署名済みregdb候補のboot_a書込みは未実施。100MHz/no-CQEのboot_aは保持されている。次はユーザーによる電源サイクル後に管理経路と実起動slotを確認し、復帰してから再開する。
