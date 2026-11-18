# C号機 MLO受入試験チェックリスト

このチェックリストは、802.11be MLOの実通信判定用。能力表示だけでPASSにしない。6GHz RFは別の認証・規制ゲートがPASSになるまで実行禁止。

## 前提ゲート

- [ ] A号機は読み取り専用で比較し、設定・再起動・通信状態を変更していない。
- [ ] C号機の管理LAN/SSH/UARTが試験中も維持できる。
- [ ] C号機のeMMC/CQE状態が安定し、試験ログと設定を安全に保存できる。
- [ ] C号機の正確な個体ラベル、型式認証、屋内外条件、許可電力、許可チャネル幅が確認済み。
- [ ] 起動時に署名済みregulatory DBが適用され、対象6GHz channelがkernelから利用可能と確認済み。country codeを強制していない。
- [ ] 実機`iw phy` Radios inventoryとdriverソースで5GHz/6GHzの同時radio割当てを確認済み。
- [ ] 校正値はC号機自身由来で、デフォルトEEPROM等による代用がないことを確認済み。
- [ ] 802.11be MLO対応STAを確保。各link能力を端末仕様と接続後statusで確認する。
- [ ] 320MHzをAP/STAのいずれにも設定していない。

## MLO構成の確認

- [ ] APのMLD addressと2つのlink IDを記録。個体識別情報は公開ログから除外。
- [ ] 5GHz linkが実際に160MHzで動作し、primary/center channelとwidthを記録。
- [ ] 6GHz linkが実際に160MHzで動作し、許可されたprimary/center channelとwidthを記録。
- [ ] STAが単一のMLDとして両linkに関連付けられている。単なる2つの独立STA接続ではない。
- [ ] AP/STA双方のper-link statusに2つのactive link IDを確認。
- [ ] 各link単独でARP/IPv4/IPv6等の疎通前提を確認。

## 双方向データ受入

- [ ] Link 5 GHzのTX/RX bytes/packetsが、試験前後で両方向とも増加。
- [ ] Link 6 GHzのTX/RX bytes/packetsが、試験前後で両方向とも増加。
- [ ] MLD上のclientから外部peerへの双方向IP通信が成立。
- [ ] 5GHz link停止時も仕様どおり6GHz link経由で通信が継続。
- [ ] 5GHz link復帰後、両linkがactiveに戻る。
- [ ] 6GHz link停止時も仕様どおり5GHz link経由で通信が継続。
- [ ] 6GHz link復帰後、両linkがactiveに戻る。
- [ ] Throughput、RTT/latency、retry/lossを一定時間・一定トラフィックで測定し、コマンド・条件・結果を保存。
- [ ] 再起動後にLAN/SSHと両MLO linkの復帰を確認（独立承認された再起動段階で実施）。

## 判定

全てのbandwidth、active link、per-link traffic、実IP通信を直接観測できた場合のみ`MLO_5G160_6G160_BIDIRECTIONAL_PASS`。6GHzが未許可、radio topology不明、client非対応、または片linkのcounter/通信が確認できない場合は`NOT_TESTED`または`BLOCKED`。
