# Debian / OpenWrt差分と還元候補

Debianは2026-11-14の今回の実機観測。OpenWrtは過去実機記録、現在公開されているソース、compile-only成果を分ける。ここでの比較のためにOpenWrtを起動・flash・mainline mergeしていない。

| 機能 | 今回Debian 13 / 6.18.63 | 過去OpenWrt/純正OS | 公開移植への意味 |
|---|---|---|---|
| kernel/systemd/P44 | 実機稼働、ただしeMMC書き込み障害 | RC14/RC16系procd起動履歴 | boot可能とstorage安定は別ゲート |
| Ethernet | DSA/MT7531、LAN2 1Gbps、4MiB内容一致 | 過去6.18.44でpacket test | MAC1→SGMII1→switch CPU port5→user port1の観測をDTへ還元可能 |
| Wi-Fi 2.4/5GHz | PHY登録、MCU timeout、未接続 | RC14 C号機AP/DHCP/ping記録 | 6.18.63の校正/FW/API差の検証が必要 |
| Wi-Fi6GHz/MLO | チャネルdisabled、未試験 | 過去AP-start記述はあるが接続/MLOは未実証 | feature広告・AP-start・クライアント通信を区別 |
| LTE IPv4 | ccmni登録のみ、DOWN、未検証 | Stage10はICMP/DNS/TLS HTTPS成功履歴 | CCCI/FS/MIPC/RIL/firmwareとEthernet初期化依存を再現する必要 |
| NR/WWAN IPv6 | 未検証 | 公開証拠要約も未検証 | LTE成功から推論しない |
| GNSS | driver未結合、標準GNSS無効 | **純正B OSのみ**3D fix/4系統航法情報 | GNSS移植が必要。SBAS/L1S対応はUNKNOWN |
| Bluetooth | Linux HCI無効。ESP32-C3 AT応答は確認 | 純正にESP32制御daemon/FIFO | 外付けESP-AT制御を独立実装する余地。HCIと混同しない |
| I2C/SPI/PWM/LED/RTC/TRNG | DT記述とdriver登録の結合に不足 | 純正側には専用依存候補 | generic compatibleを推測して割当てずmatch/clock/powerを検証 |

## DTS・カーネル・ユーザー空間の差

現在公開の[独立作成board DTS](https://github.com/Karin-Laboratory/openwrt-terminal-6/blob/main/board/mt6990-air-terminal-6.dts)は、Ethernet/eMMC/PCIe/USBと関連SGMIIを安全上disabledにしているcompile-only候補。今回のDebianは所有者保持の異なるDTB/driver集合で動作している。公開DTSをそのままenabledへ変えるだけで今回の動作を再現できるとはしない。

Debian実機で追加取得した選択Kconfigは[evidence](evidence/CUNIT-KCONFIG-20261114.txt)。BT/GNSS/CPU_IDLE/IOMMU/CRYPTO_USER_APIが無効、MTK CCCI/CCMNI/MEDMCUと一部周辺driverが有効、USB/一部LEDがmoduleでもko配備が不足する。過去Stage10 configは[証拠JSON](https://github.com/Karin-Laboratory/openwrt-terminal-6/blob/main/docs/evidence/lte-stage10.json)のhashで識別できるが、公開物にはconfig全文がないためbit-by-bit差分は未完。公開デフォルトconfigと私有の実機成功configを同一視しない。

Ethernetは既存initramfsのNETSYS→MDIO/DSA→SGMII初期化、Wi-FiはP44 serviceのRAM firmware準備後のmodule bindに依存する。modem/GNSSは純正専用ユーザー空間がDebianで稼働していない。公開firmware/校正資産の再配布許可は今回確認していない。バイナリ転用を公開移植の完成条件としない。

## 優先順位

1. **P0 eMMC安全性:** CQE無効化DT候補を最初に別起動サイクルで検証。rootfsは救出側で整合性検査し、署名・復旧手段を用意。[追加解析](CUNIT-EMMC-MITIGATION-20261114.ja.md)。
2. **P1 再現可能なplatform基盤:** current DTの資源/依存と権利確認済みsourceを照合。Ethernet/clock/MMC/powerの独立DTSとmatching kernel/moduleを固定。
3. **P1 ESP32-C3 query tool:** 今回の独立実装はstdout・allowlist・排他・timeout付き。GPIO reset/scan/FW更新なしでAT制御を利用できる。
4. **P2 Wi-Fi:** firmware/同一個体calibrationのRAM一致、MCU timeout、regdbを先に解決し、その後2.4/5GHzの規制適合試験。6GHz/MLOは後段。
5. **P2 PWM/I2C/LED:** fanやLEDを実装確認してprovider依存を修正。未配線センサーの一括有効化はしない。
6. **P3 WWAN/GNSS:** 現物とsourceの依存図、IPC lifecycleと復旧性、個人情報を保護した最小応答試験を先に作る。

公開リポジトリは[STATUS](https://github.com/Karin-Laboratory/openwrt-terminal-6/blob/main/docs/STATUS.md)と[provenance](https://github.com/Karin-Laboratory/openwrt-terminal-6/blob/main/docs/PROVENANCE.md)の証拠境界を維持する。本調査は観測資料とホスト側toolの追加であり、OpenWrt本線への無断マージ・稼働firmware書換えはしていない。
