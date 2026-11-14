# 追加解析: eMMC CQE回避案と別起動サイクル

## 結論と検証状態

**第一候補はDTの`/mmc@11230000`から`supports-cqe`だけを削除すること。** 調べた6.18.63 driverではDTだけでhardware CQE選択を外せる。カーネルCコード修正はこの候補には不要。ただし、これでI/Oが安定するかは未試験であり、CQEが根本原因と断定していない。

開発VMで4種類のDTB候補を別々に作成し、全propertyとreservation mapが期待差分以外不変であることを確認した。候補DTBには所有個体由来情報があるため非公開ローカル保持。実機P25/P26/P44へ投入せず、controller再初期化もしていない。

## ログと因果関係

実測の順序は`msdc_cmdq_irq: DATA TIMEOUT ERR` → dat_err=-110 → CQE recovery反復 → block層WRITE I/O error → ext4 unwritten extent変換失敗 → sync失敗。新規パッケージ2ファイルで実データ破損も確認した。ext4は下位I/Oエラーを受けて失敗しており、現時点で「ext4固有バグ」が先行原因という証拠はない。

書き込み先アドレス/長さ、CQHCI descriptor、DMAバリア/アドレス幅、割り込みack、CQE/legacy切替、タイムアウト計算、HS400 signal/tuning、電源/温度は候補に残る。CMD12 recoveryログだけでカード故障や特定のDMA命令が原因とは断定しない。再起動の直接原因となるpanic traceは取得できていない。

## 実機と保持ソースの対応

稼働カーネルのreleaseと`#3 SMP Thu Nov 12 17:49:50 JST 2026`が保持済み6.18.63 build treeと一致。展開した/proc/config.gzのSHA256も保持.configと一致:

`b164811ae1a5246c694b641323f96e2e8f1842342529aea8e858dddb80f9887d`

調査対象ソースの識別hash:

| ファイル | SHA256 |
|---|---|
| drivers/mmc/host/mtk-sd.c | 8410e325929c9379a781e46e8539411087a169f3526e3b90952e51b11076ecbb |
| drivers/mmc/host/cqhci-core.c | 1650f49961de1b304750bb849bde8335ff1266756b19a46bafe249714f4a239a |
| drivers/mmc/core/mmc.c | 3fd819d40cb6aa118a3689a1ee82041383a64506546f4e5faee308fc63d1949d |

release/config一致は稼働Image全バイトの再製造証明ではない。保持済みvendor-capableソース全体を公開リポジトリへコピーしていない。ソース抜粋だけでdriverの全権利状態を保証しない。

`msdc_of_parse`（mtk-sd.c 2916付近）はsupports-cqeを読んでhost->cqhciを選択。probeの3097付近はその値がtrueの場合だけMMC_CAP2_CQE/DCMDを立て、3137付近でCQHCIを初期化する。MMC core（mmc.c 1919付近）はcardがCMDQ対応かつhostのCQE capがある場合にCMDQを有効化する。

**削除構文が必要。** DT booleanを`supports-cqe = <0>`に変えても、propertyが存在するのでtrueと解釈される。runtimeでblock queue/EXT_CSDを推測して切り替える方法は使わない。

CQEを外すとこのdriverではHost Software Queue（HSQ）へfallbackする可能性がある。HSQとcard hardware CMDQは別で、`Host Software Queue enabled`が出てもhardware CQE無効化の失敗とはしない。

## 純正5.4.238との比較

所有者保持の2026-10-31 C号機P38 boot_b captureから、開発VM上だけでgzip kernelとDTメタデータを確認した。kernel版は5.4.238。msdc_cmdq_irq、supports-cqe、CQHCI関連の文字列があり、純正kernelにもCQE実装経路が含まれる証拠となる。これだけで純正runtimeでCMDQが有効だったとはしない。

| 項目 | 純正P38保存物 | Debian稼働DT/実測 |
|---|---|---|
| MMC node全property | /mmc@11230000 | **全propertyのraw値が一致** |
| compatible / reg | mt6990-mmc、0x11230000/0x11f00000 | 一致 |
| clock参照/名 | source/hclk/axi_clk/ahb_clk | 一致。provider内部設定や実clock rateの一致は未実証 |
| 転送宣言 | 8bit、最大200MHz、HS200/HS400/DDR1.8V | 一致 |
| supports-cqe | propertyあり | propertyあり、runtime cmdq_en=1 |
| 実転送 | 純正runtimeの新規測定なし | HS400、actual 189,999,931Hz |
| driver実装 | stock ImageにCQE文字列あり。正確なvendor5.4ソース対応は未確定 | 保持6.18.63ソースの上記経路を確認 |
| 初期化 | 保存DT/起動kernelを静的確認 | clock ungate→HW初期化→CQHCI/HSQ→mmc_add_host→カード初期化 |

手元にあるvanilla 5.4.238のmtk-sd.cはMT6990対応の純正driverではないため、これとのdiffを「純正対Debianの差分」としていない。**純正vendor driverのDMA descriptor/timeout/tuning全実装との行単位比較、純正runtimeのEXT_CSD/ios/clock測定は未完**。安全な別の純正起動サイクルと対応sourceの確定が必要。

## EXT_CSDの読み取り

現在rootのPARTNAME=rootfs_dataを確認して実際のmmcblkNを導出し、`mmc extcsd read`（標準MMC ioctl/CMD8）だけを実行。controller再初期化やEXT_CSD writeコマンドは実行していない。

- CARD_TYPE=0x57、HS_TIMING=0x03、SEC_COUNT=0x00748000。
- CMDQ_SUPPORT=1、CMDQ_DEPTH=16。
- sysfs cmdq_en=1。EXT_CSD出力のCMDQ_MODE_ENは0だが、mmc-utils自身がruntime状態はsysfsで確認するよう注意する。単一EXT_CSD値で「CQE無効」と誤判定しない。
- CACHE_CTRL=1、BKOPS_STATUS=0、BKOPS_EN=0、HPI_MGMT=1。
- LIFE_TIME A/B=0x01/0x01、PRE_EOL=0x01。粗い寿命情報であり今回のI/O異常の反証ではない。

## 独立した4候補

| 候補 | 変更するもの | 変更しないもの | 検証する仮説 |
|---|---|---|---|
| **no-cqe（最初）** | supports-cqe削除 | 周波数、HS400/HS200、bus/power | HW CQE経路を外した時の安定性 |
| max100 | max-frequency=100MHz | CQE・mode宣言 | clock低下による安定性。実際の選択clock/modeを再測定 |
| no-hs400 | HS400/ES capability削除 | CQE、max-frequency | HS200等へのfallback。選択結果は起動後確認 |
| no-hs200-hs400 | HS200/HS400/ES capability削除 | CQE、DDR1.8/highspeed | legacy/DDR52系との切分け |

初回から複数候補を組み合わせない。CQE無効化でもlegacy DMAは使うため「DMA全部を無効にする」案ではない。周波数だけを下げてもHS400/電圧/tuningの全依存を解消する保証はない。

## パッチとホスト側検証

- [no-CQE DTS fragment](../../patches/mmc-no-cqe.dtsi): base DTSの後にincludeする静的ソース用。`/plugin/` runtime overlayではない。
- [厳密なDTB変換tool](../../scripts/fdt_mmc_policy.py): input SHA256、controller compatible、8bitを検査し、新規出力だけを許可。fdtput後、全propertyとreservation mapの期待差分を照合する。
- 実機取得したowner-private DTBに4候補を適用しsemantic検査PASS。合成fixtureへのcompile/negative testも実施。**hardware testは全てNOT_RUN。**

tool使用例（開発VMの私有領域だけで実行）:

```sh
python3 scripts/fdt_mmc_policy.py owner-private-input.dtb owner-private-no-cqe.dtb \
  --sha256 INPUT_SHA256 --policy no-cqe
```

DTBには個体情報を含むため出力やその識別hashを公開成果物として自動uploadしない。LKによるDT上書きがあり得るため、後日の起動時には実際のsysfs DTでsupports-cqe不在を確認する。

## 別の安全な起動試験サイクル

1. 現行管理経路と純正B救出経路、署名可能な製造手順、UARTローカル復旧を独立に確認。P44のデータ救出を先に行い、試験rootはRAM/別媒体を優先。
2. no-cqeだけの候補を別途レビュー・署名・製造し、未検証kernelを現在のdeviceへ書かない。本依頼でflashしない。
3. 起動後にcontrollerのDT、cmdq_en=0、hardware CQHCI非選択、iosのclock/mode、driver logを確認。HSQをCQEと混同しない。
4. 現行P44への書き込みはまだ行わず、読み取り健全性と管理経路を確認。P44は未マウント救出環境でfsckの読み取り検査・必要な修復計画を立てる。
5. その後に別途許可・保存先を確定した限定scratch媒体でwrite→fsync→再読出しhash→電源/再起動後hashを段階試験。初回エラーで中止・ログ回収。
6. no-cqeが不十分な場合のみ、元条件へ戻して次の独立候補へ進む。勝手なeMMC初期化・GPT変更・eFuse/OTP設定はしない。
