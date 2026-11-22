# ① 共通ローダーv1.0：4号機 Golden GSW 実機G4未達フィードバックと最小修正（2026-11-23）

## 1. 事実と試験境界

- **実機は4号機のみ**。C号機はDebian 13基準機として保存、接続・操作なし。
- 指定署名済みGolden GSW P25、32MiB、SHA-256 `619c921f75e520a744185a0a5e2beed67f71543cc9d857ffa8eed5649f663ca2` を4号機`boot_a`に投入。機器/raspi4の全量readback・SHA・バイト比較 **PASS**。
- **G1** LK署名/ Linux 6.18.63 / RAM rescue **PASS**。
- **G2** UARTシェル・`help` **PASS**。
- **G3** MMC probe、カード認識、GPT/PARTNAME列挙 **PASS**。P26 ext4設定は未達のためRAM rescue。P43読取り専用確認。P26/P44未変更。
- **G4 LAN2 FAIL**。DTには有効な`/gsw@0`が存在するが、そのplatform bindとEthernet netdevを確認できず。ARP 3送信/応答0、ICMP 3送信/応答0。FTRACEイベント5つをONにしたがバッファ記録0、単独でprobe未実行やDMA故障を証明するものではない。
- G5 SSH、kexec/Debian：**NOT_TESTED**。
- 4号機は純正slot Bに復帰。B `success=1`、隔離LAN ping 3/3、既知ホスト鍵を用いた厳格SSH、`boot_b`全量SHA `9c6a4302861542a87152fcba1dba05e370826b916ee121174caf006281f7d6ba`一致 **PASS**。
- `boot_b`、LK、GPT、P26/P43/P44、OEM/NV/calibration等の変更なし。
- 原本UART・pcap・readback・manifest：非公開raspi4 `/home/masataka/private/unit4-golden-gsw-20261123/` のまま。公開リポジトリに転記しない。
- [PR #46 実測コメント](https://github.com/Karin-Laboratory/Debian13-Terminal6/pull/46#issuecomment-7087588055)。

## 2. 確定した静的な不整合

[元のC/KVM Golden FDTおよび同一候補kernel.configと保存済みLinuxソースのSHA固定監査](https://github.com/Karin-Laboratory/SBAT6A-Offline-Archive/actions/runs/45085716447) は **SUCCESS**。静的に次を確認した。

- `CONFIG_NET_DSA=y`、`CONFIG_NET_DSA_MT7530=y`、`CONFIG_NET_DSA_MT7530_MDIO=y`、**`CONFIG_NET_DSA_MT7530_MMIO=y`**、`CONFIG_NET_DSA_TAG_MTK=y`、`CONFIG_NET_MEDIATEK_SOC=y`。**MMIOドライバのKconfig無効化ではない**。
- 保存済み`mt7530-mmio.c`の`of_match_table`は`airoha,an7583-switch`、`airoha,en7581-switch`、`econet,en7528-switch`、`mediatek,mt7988-switch`。**`mediatek,mt753x`はない**。
- Golden FDTルート`/gsw@0`は`compatible=mediatek,mt753x`で`status=okay`、`reg`なし。つまり、**上記upstream MMIO platformドライバはこのノードを自動bindできない**。Kconfigだけの修正やOF compatible文字列の置換、存在しないMMIO `reg`の推測追加は不適切。
- Golden FDTの`/netsys@15100000`は`mediatek,mt6990-netsys`のみ、`simple-bus`、`#address-cells`、`#size-cells`がない。配下`ethernet@15100000`は`status=okay`だが、標準OF platform子ノード展開にはバス設定が必要で、**Ethernet MAC netdevが生成されない現象に整合する**。
- 旧4号機の実験FDTはNETSYSのバス設定を追加し、別MDIO `switch@1f`も追加していた。そのときLAN2 netdevは登録されたが、ARP/ICMPは未達。**デバイス登録成功とネットワーク通信成功は分けて判定**する。

これらは静的コード・DTB証拠であり、物理的なMMIOマップ、スイッチ品種、PHY/PCS/DMAの故障を証明しない。Golden GSWが本来legacy swconfig `mt753x`ドライバ経由で制御される可能性を排除できず、upstream DSA/MMIOとの安易な同一視は禁止する。

## 3. 根拠のある最小修正を診断候補として製造

新しい非公開開発ブランチ：[GSW bind/NETSYS診断](https://github.com/Karin-Laboratory/SBAT6A-Offline-Archive/tree/codex/c4-g4-gsw-mmio-ofmatch-fix-20261123)。

実機G1/G2を通ったGolden GSWカーネルgzipと内蔵initramfs、既存`/gsw@0`とMAC・PHY/SGMII等の全FDTノード/プロパティを保持したまま、**NETSYS親にだけ**以下を追加した。

- `compatible = "mediatek,mt6990-netsys", "simple-bus"`
- `#address-cells = <2>`
- `#size-cells = <2>`
- 既存の空`ranges`は保存し、他ノード/プロパティに変更なし。
- 新MDIO switchノードを重複追加しない。
- boot-v2外部ramdiskは引き続き0。Android boot IDのみ正規再計算し、署名領域はゼロ。

**これは`Ethernet platform child creation`を検証するための診断的な部分修正であり、`mediatek,mt753x`のbind、LAN2 netdev生成、ARP、SSHを保証しない。**

新しい未署名P25 SHA-256：

`23080614c990e56af7817dde9d666065543346bbcbf6a31bae1659cfd94e00fb`

- サイズ：33,554,432 bytes
- 非公開製造Actions #45085981233 **SUCCESS**
- 2回の独立製造はbyte一致、別実装のFDT全量差分/boot-v2/boot-ID/署名領域検査 **PASS**。
- 非公開Draft Release **ID `454843216`**、未署名P25 asset ID **`780882311`**、BUILD-RECEIPT asset ID **`780882415`**、SHA256SUMS asset ID **`780882452`**。
- 3件ともReleaseのasset IDで再ダウンロードし、バイト一致とSHA照合 **PASS**。
- 署名 **NOT_EXECUTED**、4号機実機再試験 **NOT_TESTED**、C号機操作 **NOT_EXECUTED**。

## 4. 次の優先課題

第一は**実機で確認された『Golden FDTではMAC platform netdevが存在しない』境界**。新バス定義によってMAC/NETSYSのplatform deviceが生成されるかを検査する。第二は**legacy `mediatek,mt753x`の実際の対応ドライバ/初期化パス**と、DSA経路との違いをソースで監査する。現状upstream `mt7530-mmio`にmatching compatible/有効なMMIO資源がない以上、OF aliasだけの変更を修正として製造してはならない。

次の実機試験は4号機のみ、別途**新しいunsigned SHAに対する署名承認**と有限boot_a試験の所有者承認が必要。ブートとP26の回帰を先に確認してから、platform device→MAC netdev→GSW/MDIO→DSA→lan2→ARP/ICMPを個別判定する。最初のFAILで停止し純正Bへ戻す。C号機は保管継続。

**状態：`G4_FAIL_DIAGNOSTIC_EVIDENCE_CAPTURED` → `UNSIGNED_NETSYS_CHILD_ENUM_DIAGNOSTIC_PRE_SIGN_PASS`。G4修復完了とは異なる。**
