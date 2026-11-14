# Device Tree棚卸しと未知ハードウェア候補

## 探索範囲

稼働sysfsのDT全881ノードを走査し、compatibleを持つ433ノード、reserved-memory直下32ノードを分類。platform 335件中40件にdriver symlinkあり、295件にはなし。PCI=4、MDIO=6、MMC=1、rpmsg=1、USB/I2C/SPI/SDIO=0という列挙結果だった。serial-baseのttyS登録はplatform側にあるため、`/sys/bus/serial/devices`が0でもUART不在とはしない。

公開[DT JSON](evidence/CUNIT-DT-INVENTORY-20261114.json)は879ノード。chosenとrawdataの2ノードを除外し、メタデータの許可リストだけを出力した。原本DTB/DTS、atag、識別子、校正内容は含めない。出力JSONは元のDTに代わる起動ファイルではない。

明示的disabledは`/dsi_te`、`/mhccif@12020000`、`/usb-phy`の3件。status未指定をokayとして数える場合も、無効な親・未結合バス・不足supplierの影響を別に見る必要がある。881件を搭載部品数と解釈しない。

## 重要な依存・認識差

- GPSノード名は`gps@18C00000`だが最初のregは0x18000000で、platform名は18000000.gps。名前だけで対応デバイスを探すと見落とす。
- MEDMCUのノード名と最初のregにも相違があり、15d00000.medmcuとして登録される。rpmsgデバイス1件はconsumer未結合。
- I2C/SPI/PWM/RNGはKconfigとdriver登録が存在する一方、DT compatibleの対応機種・clock・reset・powerの統合が不足する候補。別SoCのcompatibleへ安易に置換しない。
- `pwm-fan`: Could not get PWM。`11240000.mmc`: vqmmc regulator not availableでdeferred。
- USB PHYは結合するがefuse supplierへのdevice link警告。XHCI/MTU3のモジュール欠落もある。USBホストが動くとはしない。
- LVTSにnvmem cell取得警告。センサー値の取得と校正精度は別。
- 11290000.pcieのprobe -110は、列挙済みWi-Fiを接続している別の2ホストと区別する。

上流比較の入口はLinuxの[i2c-mt65xx](https://github.com/torvalds/linux/blob/v6.18/drivers/i2c/busses/i2c-mt65xx.c)、[spi-mt65xx](https://github.com/torvalds/linux/blob/v6.18/drivers/spi/spi-mt65xx.c)、[pwm-mediatek](https://github.com/torvalds/linux/blob/v6.18/drivers/pwm/pwm-mediatek.c)、[mtk-rng](https://github.com/torvalds/linux/blob/v6.18/drivers/char/hw_random/mtk-rng.c)。これら上流版のmatch tableを、改変済み稼働カーネルの完全なソースとして扱わない。登録済みdriver・未結合device・retained sourceのmatch tableを順に照合する必要がある。

## 未知・未使用の候補と反証可能な次の試験

| 候補 | 根拠 | 現在の判定 | 次の試験と反証条件 |
|---|---|---|---|
| AW9523B LED制御 | I2C 0x5bのcompatibleとLTE/SIM/Wi-Fi等LED子ノード | UNKNOWN（外付け候補） | 回路/実装写真と部品刻印を確認し、I2C controller対応後に既知安全なIDレジスタだけを読む。不在ならDTS残骸仮説 |
| PWMファン | pwm-fan DT、PWM取得defer | UNKNOWN | 非通電の物理観察・接続資料・PWM provider対応を先に確認。DTSだけでファン搭載断定しない |
| 追加MMC/SDIO | 11240000.mmc、regulator不足 | UNKNOWN | 回路と電源供給を確認。未実装なら無効化候補。既存eMMCホストと番号で混同しない |
| PMIC RTC | MT6685配下RTCノード、rtc classなし | UNKNOWN | SPMI/PMICの物理実装とdriver経路を確認。根拠なくPMICレジスタへ書かない |
| PMIC MT6319/6361/6685 | SPMIのcompatible記述 | UNKNOWN | 純正のdriver bind/runtimeと基板資料で同定。全ノード同時実装と仮定しない |
| センサー類 | barometer/gsensor/msensor/alsps、cap_touch等のI2C DT | UNKNOWN | 対象型番の部品・純正probe証拠が得られなければSoC開発ボード共通記述候補 |
| 音声/Proslic | SPIのsilabs,proslic_spi、AFE/multimediaノード | UNKNOWN | 外部接続と実装を確認。音声出力やSPI無差別probeは行わない |
| TRNG/EIP97 | 0x1020f000/0x10320000にDT、未結合 | BLOCKED | 正しいmatch/clock/resetと安全な標準driverでknown-answer試験。CPU暗号命令と区別 |
| Mali/multimedia | mali/disp/codec類のDT、多数未結合 | UNKNOWN | SoC SKU・純正driver使用・部品仕様を照合。未結合数だけで故障扱いしない |
| MEDMCU/rpmsg consumer | mailbox IRQ、rpmsg列挙 | DRIVER_LOADED | 文書化されたIPCの応答を取得して初めて機能VERIFIED。firmwareが起動済みかは別 |
| ESP32-C3 | UART1応答とESP32C3/MINI-1版表示 | VERIFIED（追加調査） | [ESP32報告](CUNIT-ESP32-C3-20261114.ja.md)。Linux HCIとは別のAT制御 |

## 限界

未認識・probe失敗・supplier不足・disabled・firmware欠落を分類したが、未知のMMIO読み書き、I2C全アドレス探索、電源/clock変更、無線scanはしていない。したがってDTにない外付け回路や、電源OFFの部品を発見し尽くしたとは主張しない。eMMC不安定性を優先し、今後の追加driver配備と高負荷試験は別サイクルに分離する。
