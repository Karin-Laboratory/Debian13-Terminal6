# 共通ローダー v1.0: 最小P25製造・実機受入前手順（試作、2026-11-21）

**状態：SOURCE_CANDIDATE、署名なし・実機未適用。**
本ブランチは、現行C号機の起動実績P25 `74c1c98b...` と本線のP44 ZIPを**改変せず**、署名直前の未署名P25を独立製造する作業用。製造してもLKでの署名済起動は証明されない。実機に`dd`せず、署名をしない。

## 原則

- **設計意図の補足（非公開・閲覧権限が必要）：** [最小P25＋kexec方式の技術判断と注意点](https://github.com/Karin-Laboratory/Chappie-Memory/blob/main/terminal6/SoftBank-Air6-%E6%9C%80%E5%B0%8FP25-kexec%E6%96%B9%E5%BC%8F%E3%81%AE%E6%8A%80%E8%A1%93%E5%88%A4%E6%96%AD%E3%81%A8%E6%B3%A8%E6%84%8F%E7%82%B9-20261121.md)。LK改造案・純正Linux＋kexec-mod案との比較、kexec後段の正確な責任範囲、eMMC/DTB/watchdogなどの残存ハードウェア状態、署名と信頼境界を整理した実装参照資料。**仕様変更や実機PASSの根拠にはしない。**
- 非公開確定仕様 `Karin-Laboratory/Chappie-Memory/terminal6/SoftBank-Air6-共通ローダー確定仕様-v1.0-20261121.md` に従う。公開Debian憲章v1.4には未反映で、互換性を主張しない。
- P25は単独initramfs（rootfs_data/P44への強制切替なし）。内蔵: UART、eMMC PARTNAME検出、ext4、管理LAN2、SSH、kexec、OS選択スクリプト。
- P26 rootfs_a はext4なら設定/SSHホスト鍵/認証情報を保存。空または現行SquashFSなら**フォーマットしない**。RAM上だけの無認証root SSHを管理LAN2固定IPv4に開くため、**絶対に物理隔離のないネットワークへ接続しないこと**。SSH初回登録は`passwd root`または`authorized_keys`、P26がext4のときのみ永続化を想定。
- P43 user_dataは`ro,noload`で読取専用、OSの`Image`・`board.dtb`・任意`initrd.img`を`terminal6/<OS>/`から読み込む。
- P44は任意。P25起動に必要ない。stock B、boot control、P43/P44のGPTや内容は変更しない。モデム/PCIe/無線/USB/KVMのP25組込みは禁止。
- 現行C号機に安全に戻るための資産固定台帳：`Karin-Laboratory/Chappie-Memory/terminal6/CUNIT-DEBIAN-P25-P44-ROLLBACK-PIN-20261121.md`（非公開）。**最新P44-install.zipは実機未導入候補であり、現行P44実物のバックアップは別ゲート。**

## ビルド設計
1. 公開SHAピン留めLinux v6.18.63＋MT6990 OSS networking stagingを使い、`terminal6-lean`から最小 profileを派生。PCI/USB/無線を無効化し`CONFIG_KEXEC=y`を加えた`-t6-minimal-loader-v10` ABI。
2. ネイティブARM64上で`scripts/build-loader-initramfs.sh`により BusyBox、Dropbear、dropbearkey、kexec-tools、および**BusyBoxに無いutil-linux blkid/mountpoint本体と依存ELF**をinitramfsへ同梱。`tests/smoke-loader-initramfs.sh`がARM64の隔離chrootで実行検査し、ext4/SquashFS/破損/未存在を識別する。起動後に固定鍵はなく、P26がなければRAM host keyを生成。
3. `scripts/build-linux-6.18.sh`に`KERNEL_PROFILE=terminal6-lean`、独立initramfsを渡す。
4. 公式publicドナー由来のAndroid boot v2 packerと標準AOSP DT tableで、32MiBのunsigned P25を組立て。**DTBは非公開ARM64製造CIでC号機起動実績済みP25をSHA固定で検証して抽出した実績版FDTを採用**。公開の実験用FDTは差分監査用に限定し、非公開FDT/端末情報を公開Gitへコミットしない。C号機での新最小カーネルとの互換性は別ゲート。
5. 別経路verifyで全32MiB SHA、gzip kernel、DT table、Embedded initramfs role、0 padding、署名用後尾余白を独立検査。
6. **非公開** build runnerでcandidate imageとSHA receiptをDraft Releaseへ保存し、再取得・全長SHA照合する。CIの完走とSHAが得られるまで、署名直前完成とは記録しない。

## P26の設定ファイル（実機未検証）
```text
/config/boot/boot.conf:
default=debian
next=
autoboot=1
timeout=15
/config/boot/entries/debian.conf:
kernel=terminal6/debian/Image
dtb=terminal6/debian/board.dtb
initrd=terminal6/debian/initrd.img
cmdline=console=ttyS0,115200n8 root=... 
```
OSはP43の専用ディレクトリに展開する。次回だけ起動先`next`はkexec_load成功後、`kexec -e`前に消費。P25上のUARTまたはSSHで`touch /run/terminal6-hold`すれば待機後のautobootを停止。失敗時に自動rollbackは行わない。

## ハードウェア受入ゲート（未達）
- **未達 1：** P25起動単独でeMMC、lan2実ARP/IP/SSH。現行C号機のP25が起動するからといって、この新Imageの互換性を保証しない。
- **未達 2：** 初回の隔離LAN/無認証root経路、P26 ext4認証永続化、P26無しでも管理シェル/SSH。
- **未達 3：** P43読取と次回限定の`next`消費を含むOS選択、別途ビルドしたunsigned Imageへ`kexec`後の第2段Linux SSH接続。
- **未達 4：** retry=0/success=1の正規ブートAPI（安全性を解析するまで**実装/書込みせず**）。純正slot B完全無変更、手動復旧。
- **未達 5：** kexec移行時のP26/P43アンマウント・デバイスquiesceの実機安全性。モデム/PCIeの現象をブラックリストの恒久仕様にはしない。

**備考**：これは仕様確定v1.0に基づいた試作であり、製造CI PASSだけで署名・実機導入承認を求めない。

## 2026-11-21 再製造修正と署名前監査方針

旧版 `fc4da7fa1a283d70badf8ec9cca866b2a81fd1c04c68774aa455f33f1fc82fe5` はBusyBoxの`blkid/mountpoint`アプレット欠落で **DO_NOT_SIGN**。この旧実物を上書きせず、次回CIでは別SHAの新candidateを製造する。

- 実物helperの動作確認は`tests/smoke-loader-initramfs.sh`で**デバイスに触れず**オフラインfixtureを使用。
- `console=ttyS0,115200n8`を実機成功版に合わせる。
- 非公開CIで比較するDTB: 実績 `a6bef90e18c0a16934e6c4196fea60408a1fed08b6ef9b62c7fbe5d7c5632d91`、旧実験 `94a789069858be6c35df60ae940c4a476ab3cba5b7fdd2049093b5a3af34f551`。差分はUART/MMC/95MHz clock/MT7531/SGMII1/DRAM reserved memory/PSCI等の**機能条件**を中心に検証。実績版の再利用は同一新カーネルの起動保証ではない。
- G3のslot A `retry=0,success=1`正規API実装とreadback、実機起動・SSH・第2段OS起動はなお未達。PASSを偽装しない。
- 新候補を署名する前に、現行C号機のP44 ext4オフラインスナップショット・純正B復旧導線も再検証する。
