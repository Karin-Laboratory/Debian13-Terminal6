# C号機 KVM成功版MMC0のOSS復元実験（2026-11-19）
目的: 11/16実機KVM成功版の `/mmc@11230000` の pinctrl 参照と `CONFIG_PINCTRL_MT69XX=y` を、新しいLinux 6.18.63へ一組として戻す。
直接の失敗: 11/19署名済みP25は `mtk-msdc 11230000.mmc: probe ... error -110`。MMCブロックデバイス無し。原因はまだ確定していない。
このブランチの変更: `T6_ENABLE_MT69XX_PINCTRL=1` でのみ、上流公開OSS `13179415360/openwrt-mt6990-lg6851f` 固定コミット `a40df9a5afb46716dea799acea69f17480df4d82` の0521～0524 patchをGit blob SHA検証後に順番に適用。MT69xx providerをbuilt-inにする。デフォルトの公開ビルドは変更しない。
ライセンス: 移植元の新規ドライバはGPL-2.0 SPDX。元patchを改変せず取得し、出自を固定する。
C号機固有のKVM実機成功FDT (SHA256 `a6bef90e18c0a16934e6c4196fea60408a1fed08b6ef9b62c7fbe5d7c5632d91`) はこの公開ブランチに含めない。非公開の別buildで無改変のFDTと組み合わせる。
別途: P25/P44カーネルモジュールを同じABIで製造し、boot-v2署名余白・全量SHA・GitHub private保全を検証する。署名/実機書込/slot切替/再起動/RFは別承認。CI製造は実機起動成功を意味しない。
