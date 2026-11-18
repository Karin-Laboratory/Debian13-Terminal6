# 第4号機 Bluetooth/BLE 読み取り専用調査（2026-11-18）

## 判定

**C：純正MediaTek UART Bluetoothドライバーは存在するが、MT6990側BTコントローラーの実装・配線は未確認。** 第4号機の純正slot B（Linux 5.4.238）で `btmtk_uart` と `bluetooth` はロード済みだが、HCIデバイスは0件。これは「BTハードウェアなし」の証明でも「使用可能」の証明でもない。DebianのBLE HID使用可否は現段階で **BLOCKED**。

## 原本と実測

| 対象 | 実測 | SHA-256 |
| --- | --- | --- |
| 第4号機 live `btmtk_uart.ko` | 95,400 bytes、AArch64 ELF REL | `fc47fcb2acedde628a0d7bbce19c3526d11a3863948ffd703486fcd27642b2d4` |
| 第4号機 live FDT | 177,554 bytes | `af2be78d187e165da7fb966eac5b465929a2189457067fc61e62a08d35af17d7` |
| 純正 `/lib/firmware/mt7915_patch_e2_hdr.bin` | 618,358 bytes | `9eeb59d9fa8f7a6d4791c6b2f7644ee2723a9fbf54b1d5a7b95206062934939c` |

生モジュール・FDTはowner-privateの `terminal6-unit4-bt-readonly-20261118` にのみ保存。GitHubには含めない。第4号機は `bootslot=b`、機種 `MediaTek evb6990_cpe_mt7990_emmc`、Linux 5.4.238を接続時に確認した。調査ではSSHの読み取りコマンドだけを使用し、UART・GPIO・モジュール・設定・eMMCには一切書き込んでいない。

`lsmod` は `btmtk_uart`、`bluetooth`、`conninfra` を表示したが、`/sys/class/bluetooth` は空。`/proc/tty/ldiscs` に `n_mtk 16` はある。`/proc/tty/driver/serial` では ttyS0=`0x11002000`、ttyS1=`0x11003000`、ttyS2=`0x11004000`。ttyS0 はコンソールgetty使用中。ttyS1にRXカウントがあるが、BT接続の根拠にはならない。候補UARTは **UNKNOWN**。

FDTには3本のUARTがあるが、BT子ノードや明示的BT/BTIFノードは確認できない。名前検索の陰性をハードウェア非搭載の根拠にしない。対応する電源・GPIO・ピン設定・基板配線も未確定。

## HCI未登録の機構

第4号機の実モジュールをAArch64逆アセンブルした。`init_module` は `btmtk_cif_register` を呼び、同関数の `.text+0xc7c..0xc80` は番号16で `tty_register_ldisc` を呼ぶ。一方、TTY open側の `.text+0x248` から `btmtk_allocate_hci_device` を呼び、後者の `.text+0x5c80` が `hci_register_dev` を呼ぶ。よってモジュールのロード自体はHCI登録を意味しない。現在はline discipline登録まで確認できるが、どのUARTに接続すべきか、その接続が実施されたか、コントローラーが応答するかは未確認である。ファームウェア名はモジュール内文字列と純正パッケージMakefileの両方で `mt7915_patch_e2_hdr.bin` と一致するが、**第4号機の実コントローラーにロードされた証拠はない**。

純正rootfsの `knos.flags.bluetooth=0` と `/etc/init.d/esp32_controllerd` はGPIO 382と `esp32_controller --adv` / `at+bleinit=0` を扱う。これはESP32側BLEの制御で、MT6990 HCIが登録済みという意味ではない。純正公開OSSのパッケージ定義は `btmtk_uart` を自動ロードするが、実ドライバーソースの参照先は公開ツリー内に無い。このソース・再配布権は未確認。

## Debian 13 / Linux 6.18.63

保存済みのDebian 6.18.63カーネル設定では `# CONFIG_BT is not set`。その構成ではBlueZ導入だけでHCIソケットは使えない。Linux 6.18.63ソースには `BT_MTKUART`（serdev依存）、`BT_HCIUART`、`BT_MTK`、`BT_HCIUART_H4` があるが、`btmtkuart.c` のOF matchは `mediatek,mt7622-bluetooth`、`mediatek,mt7663u-bluetooth`、`mediatek,mt7668u-bluetooth` に限定され、MT6990専用の記述はない。純正のout-of-tree `n_mtk` ドライバーをそのまま6.18.63へ挿入することもABI上できない。上流ドライバーで当該コントローラーを扱えるかは未証明。Kernelの[MediaTek BT DT binding](https://www.kernel.org/doc/Documentation/devicetree/bindings/net/bluetooth/mediatek,mt7622-bluetooth.yaml)もMT6990の配線を示していない。

最短の次工程は、(1) 第4号機の基板・純正設定・回路情報または純正BT UART起動手順からコントローラーとTTY配線を確定、(2) 対応チップ・必要ファームウェア・ライセンスを確認、(3) DebianでBT/HCI UART/MediaTek/BlueZ/HIDを有効にした隔離ビルド、(4) 管理経路を保持した別途承認済み実機試験でHCI登録、LE scan、BLE HIDペアリング・キーボード/マウス入力を段階検証すること。確認前にttyS0/1/2へ送信しない。

## 未解決事項と限界

- MT6990側に実BTコントローラーが実装されているか、MT7990との結合か、UART候補、ピン、電源、WMT起動手順は未確定。
- `mt7915_patch_e2_hdr.bin` の実機でのロード有無、当該ハードとの適合、再配布権は未確定。
- 純正out-of-treeモジュールのソースは公開ツリーに無く、6.18.63への移植規模は **高・未確定**。まず配線とチップIDの証拠が必要。
- 第4号機には予期しない再起動履歴があるため、今回の調査は低負荷の読み取りに限定した。BLE実通信は **NOT_TESTED**。
