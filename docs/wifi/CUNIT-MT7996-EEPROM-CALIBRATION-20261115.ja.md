# C号機 MT7996 EEPROM校正転送の実機修正 (2026-11-15)

## 結果

C号機のWi-Fi初期化を止めていた原因は、EFUSE_CTRL MCUコマンドの応答待ちが20秒で打ち切られていたことだった。初回の修正版でも、起動後約20秒で最後のEEPROM buffer page (8/8) が `-ETIMEDOUT` となった。MediaTek/OpenWrt mt76の後続修正は、この起動時校正コマンドのtimeoutを30秒に延長し、ベンダードライバに合わせている。30秒設定へ変更した再起動では、C号機自身のOTP校正値46バイトをEEPROM RAM bufferへ統合し、8ページすべてのfirmware ACKを確認した。起動後の追加確認でもMCU timeoutとページ失敗は記録されていない。

この結果で確認できたのは、C号機固有OTPから読み取ったcalibration-free値の統合と、OEM EEPROM buffer全ページのfirmware受理である。RF送信、AP/STA通信、規制データロード、6GHz利用は未確認のまま区別する。

## 実測

| 項目 | 実測 |
|---|---|
| 対象 | C号機、Debian 13、Linux `6.18.63-debian-t6-proto2`、slot A |
| PCI / driver | MT7990 core/HIF (`14c3:7990` / `14c3:7991`)、`mt7996e` / `mt7996e_hif` |
| PHY | `phy0` 1基。2 endpointを別PHYとは数えていない |
| firmware | WM/WA build `2024-05-10`、DSP build `2023-11-13` |
| EEPROM fallback | C号機自身のstock rootfs_b由来7680-byte EEPROMを、要求名 `mt7996_eeprom_2i5i6i.bin` で選択 |
| 校正統合 | `merged 46 OTP calibration-free bytes into EEPROM buffer` |
| firmware upload | `uploaded all 8 EEPROM buffer pages`。前の20秒設定では8/8でtimeoutしたが、30秒設定後は全ページ完了 |
| 再起動 | 30秒timeout設定を含むモジュールで通常再起動し、PHYサービス、SSH、PCI bindが復帰。追加採取時点まで新しいEFUSE_CTRL timeoutなし |
| 無線状態 | `wlp1s0` は managed / DOWN、TX packet counter 0。RF送信なし |
| regulatory | 起動時に `regulatory.db` がロードされず。6GHzの利用・送信は試していない |
| eMMC | 100MHz上限、実クロック `94,999,965 Hz`、HS400、8-bit、1.8V、`cmdq_en=0` を維持 |
| 管理 | C号機SSHが再起動ごとに約16–24秒で復帰。raspi4のUSB-UART機器は存在し設定変更なし |

## 変更

`patches/0001-mt7996-eeprom-calfree-timeout.patch` は次の差分を含む。

- EFUSE_CTRL MCU timeoutを20秒から30秒に延長。
- 対象MT7996/MT7990変種に応じた、C号機自身のADIE OTPからのcalibration-free値読み出しとEEPROM RAM bufferへの統合。
- OTP block読み込み前の一時buffer初期化。
- EEPROM upload失敗時にMAC/TXBF初期化へ進まないfail-closed処理。
- firmware page timeoutと完了数、fallbackファイル名の診断ログ。

校正値の書き込み、工場領域変更、EEPROM/NVRAM公開は行っていない。変更した実機ファイルはP44上の `updates/terminal6-mt76/mt7996e.ko` とその `MODULE-SHA256SUMS` のみ。候補モジュールSHA256は `c87f66f6573d5a4c3d1e829009fc42baf3223f1b0b958c4fc8a549b135e0fecd`。カーネル、DTB、P25、slot B、P26/P39、GPT、OEM領域は変更していない。旧モジュールとchecksum一覧はraspi4のowner-private backupに保管。

## 実装根拠

- [openwrt/mt76 commit 4edbdf3](https://github.com/openwrt/mt76/commit/4edbdf3): EFUSE_CTRL/EXT_EEPROM_CTRL timeoutを30秒に合わせる。説明では特にiPA variantでのfalse-positive timeoutを避ける目的としている。
- [openwrt/mt76 commit 224c7c2](https://github.com/openwrt/mt76/commit/224c7c2): OTPからcalibration-free dataを適用。
- [openwrt/mt76 commit b4ec73b](https://github.com/openwrt/mt76/commit/b4ec73b3355e8e6f5e201c6f7e941fc8f56acb27): OTP block読取bufferの寿命と初期化を修正。

今回のC号機ログでは、旧20秒設定がちょうど最終pageでtimeoutし、30秒設定で8ページ全てが完了した。timeout値変更の効果はC号機の再起動後に実測した。

## ビルドと適用

- Kernel source/config: 保存済みLinux `6.18.63-debian-t6-proto2` build tree。
- Build: `make ARCH=arm64 CROSS_COMPILE=aarch64-linux-gnu- M=drivers/net/wireless/mediatek/mt76/mt7996 modules -j4`。
- 結果: `mt7996e.ko` を生成。vermagicは実機kernelと一致。
- 実機反映: 現行モジュールをraspi4 private領域へバックアップし、P44内の同一module directoryだけを原子的に更新。`MODULE-SHA256SUMS` の全3行を検証後、通常再起動。
- rollback: raspi4 private backupの旧 `mt7996e.ko` と `MODULE-SHA256SUMS` を、C号機の同じP44 module directoryへ戻して `sha256sum -c MODULE-SHA256SUMS` を確認し通常再起動する。P25/slot操作は不要。

生ログと所有個体のデータはraspi4にprivate保存し、この公開記録とpatchには含めない。

## 次段階のno-RF確認

- `iw phy phy0 interface add t6ap0 type __ap` が成功し、`iw dev t6ap0 info` はtype APを返した。仮想AP interfaceはDOWNのまま確認後に削除し、`wlp1s0` はDOWNのまま、TX packet counter 0を維持した。
- [upstream hostapd 2.12](https://w1.fi/releases/hostapd-2.12.tar.gz) をaarch64向けにビルドし、バイナリをC号機の `/run` に一時転送して `hostapd v2.12` の起動確認を行った。P44へは保存せず、daemon・AP・beaconは起動していない。
- `iw reg set JP` は終了コード0だったが、`iw reg get` はcountry `00`のままで、チャネル規則は変化しなかった。これはJP規制データが適用された証拠ではない。
- upstream tarball SHA256: `f43502561c28ba47ab77e18e1a973d07361c68cc8b14178e619bd5796b70eabd`。C号機で実行したhostapd binary SHA256: `5917eb7229ca397107cbe41e047c01f6d27c5dd2575eb3a6a9f4783e789d64f8`。

AP/STA開始には、country `00`のまま送信可否が保証されないこと、regdbのinitramfs早期ロード、適用可能な認証/出力条件、データ通信可能な別クライアントが残る。raspi4のWi-Fiは現行ネットワーク接続中なので、管理経路に使うradioを切り替えてクライアントにする試験は行っていない。

## 次の工程 / 未達

- `regulatory.db` はまだinitramfsの早期ロード段階で見つからず、world rulesのまま。署名済みP25・既知の復旧経路を保持したregdb統合が必要。
- hostapdがC号機に未導入。hostapdの実機互換性とAP/STA設定が未検証。
- 2.4/5GHzであっても、適法な設定・利用可能チャネル・接続用クライアントを確認してから送信試験を行う。今回は管理ネットワーク保護のため`wlp1s0`をDOWNのままにした。
- WPA2/WPA3/PMF、HT/VHT/HE/EHT、6GHz、160/320MHz、MLO、EasyMeshの実通信はすべて未検証。
- 20秒から30秒への延長で今回のboot-timeoutは解消したが、長時間負荷・無線通信・異なる起動条件での安定性までは証明していない。

詳細ログ、module backup、個体固有情報はraspi4の `/home/masataka/private/mt7996-eeprom-fix-20261115/` に保存。
