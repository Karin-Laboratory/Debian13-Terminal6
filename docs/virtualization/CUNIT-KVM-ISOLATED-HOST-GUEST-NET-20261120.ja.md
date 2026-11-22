# C号機 KVM: 隔離 user-mode network のホスト・ゲスト通信実測

実施日: 2026-11-20 JST
対象: C号機 Debian 13.7 / `6.18.63-debian-t6-proto2`
判定: **QEMU/KVM guest・ゲスト起点通信・ホスト起点通信 PASS**。物理LAN転送は `NOT_TESTED`。

## 目的

従来の試験では、OpenWrt ARM64ゲストの起動、DHCP、QEMU仮想ゲートウェイへのpingまでを確認し、ホスト・ゲスト間のアプリケーション通信は未確認だった。今回は実LANへ接続せず、QEMU user-mode networkだけで両方向のTCP通信を確認する。

QEMUの`restrict=on`はゲストからホストや外部への通常の通信を遮断し、明示的に設定した転送だけを許す。今回の`guestfwd`とloopback限定`hostfwd`はこの明示的転送を利用した。物理NICには接続せず、Linux bridge、TAP、ホストIPv4 forwardingも使わない。[QEMU user networking documentation](https://www.qemu.org/docs/master/system/invocation.html)

## 実機条件

- C号機のDebian rootはP44 ext4、slot A。P25/P26/GPT/boot controlに変更なし。
- 管理経路は既存のstrict host-key検証付きSSHを維持。
- QEMU 10.0.13、`/dev/kvm`使用。
- 既存OpenWrt 25.12.6 ARM64 initramfs kernel: Linux `6.12.112`、35,754,496 bytes、SHA-256 `2b1f0796ec31201b609643beca48de20d75f2879104a20adba327cbaf64b5f2b`。
- ゲストはRAM上で256 MiB、1 vCPU。rootfs変更はすべて破棄されるinitramfs内。

## 実測

1. QEMUを`-accel kvm`、virt machine、virtio-net、`user,restrict=on`で起動。
2. ゲストの`eth0`を一時的にbridgeから外し、DHCPで`10.0.2.15/24`を取得。initramfsのDHCP後にdefault routeができなかったため、ゲストRAM内だけで`default via 10.0.2.2`を追加。仮想gatewayへのpingは2/2。
3. **Guest → Host:** ゲストの`wget`が`10.0.2.4:5555`へHTTP要求。QEMU `guestfwd`がCホスト上で専用の一回限りPython responderを起動し、本文`host-reply-through-guestfwd`を返す。ゲストが本文を受信した。
4. **Host → Guest:** ゲストRAM内でDropbearを一時起動。QEMUの`hostfwd`はホストの`127.0.0.1:19222`だけにbindし、ゲストのTCP/8080へ転送。CホストからSSH protocol identificationを送り、ゲストのSSH識別/banner応答を受信した。認証ログインは試していない。
5. QEMUを終了。CホストのP44 root、管理インターフェースと経路、IPv4 forwarding `0`、strict SSH接続が維持された。QEMU processなし。試験後の`dmesg`検索でMMC timeout/CQE/ext4 I/O errorは見つからなかった。`mmc err_stats` sysfsは存在せず、カウンタ検査はできなかった。

## 結果

| 項目 | 判定 | 根拠 |
|---|---|---|
| KVMでOpenWrt guest起動 | PASS | guest Linux/procd起動、QEMU `-accel kvm` |
| guest DHCP / gateway | PASS | `10.0.2.15/24`、`10.0.2.2` ping 2/2 |
| guest → host TCP | PASS | `guestfwd`経由のHTTP responder応答をguest `wget`が受信 |
| host → guest TCP | PASS | loopback限定`hostfwd`経由でSSH識別交換 |
| SSH認証ログイン | NOT_TESTED | 到達性試験のみ |
| guestから外部インターネット | NOT_TESTED | `restrict=on`の隔離を維持 |
| 物理LAN、bridge、TAP転送 | NOT_TESTED | 物理経路への接続・forwardingを行っていない |
| 長時間負荷・速度 | NOT_TESTED | 短時間の機能確認のみ |

## ネットワーク方式の選択

| 方式 | 今回の結果 | 判断 |
|---|---|---|
| QEMU user-mode / SLIRP | PASS、`restrict=on`で双方向TCPを確認 | ホストのroute/bridge/sysctlを変えずにKVM guestを実用接続できる。現段階の標準試験方式にする |
| TAP | NOT_TESTED、`/dev/net/tun`なし | 正確な現行カーネルとのABI一致を証明できる`tun.ko`も未確認。未検証moduleをロードしない |
| Linux bridge | NOT_TESTED | 物理portへL2を接続するため今回は使用しない。隔離試験用portと復旧経路を先に用意する |

QEMU user-modeのTCP疎通は確認したが、物理LAN転送、Terminal 6上のLinux NAT/forwarding、throughput、CPU負荷は測っていない。

## 再現

rootで実行する。QEMUが既に動作中、`/dev/kvm`がない、前回run directoryが存在する、または` t6kvm0 `が存在する場合、スクリプトは処理を開始せず停止する。既定のrun directoryを使い終えた場合は、スクリプト先頭の`RUN`を新しい`/run`下の一意なパスへ変更する。

```sh
python3 scripts/cunit_qemu_usernet_host_guest_test.py
```

全ログ、ゲストkernel、rootfs、server、DHCP情報は`/run`だけに置かれ、P44へコピーしない。失敗時も実行したQEMUだけを終了し、既存プロセスには触れない。ゲストHTTP/dropbearサービスはRAM上のみ。

最終の実機run r9に使ったスクリプトSHA-256: `0ad6a2f2dd4e9c3234dd2d9207f27adc9ebd747d936c4dba68fe5573832040b0`。匿名化したraw guest serial logは非公開保全先に保存し、SHA-256は`a250a4ca3842bb7c3b8438c0ea53663bda14562454d998ea631ceab65dfb1c77`。失敗したハーネス試行も非公開側に保存した。

## 試験中に直したハーネス上の問題

- virtio PCI ROM file欠落を避けるため、virtio-netをvirt machineのvirtio-mmio deviceに変更。
- QEMU consoleのEnter投入タイミング、シェルコマンドのecho文字列と実行完了markerの誤認を修正。
- disposable guestのDHCP clientがdefault routeを作らないことを確認し、ゲスト内だけに仮想gateway routeを追加。
- ゲストinitramfsにはBusyBox `httpd` appletがなかった。Dropbearが存在することを確認し、一時起動してSSH識別交換を試験した。

これらは試験ハーネス／guest構成の調整であり、C号機ホストのネットワーク、P44、モジュール、boot状態に変更はない。

## 次の段階

- 実LAN向けのTAP/bridge試験を行うには、同一ビルド由来であることを証明した`tun.ko`または`/dev/net/tun`の安全な供給、別の隔離セグメント、管理経路の独立保護が必要。
- 本実測はQEMU user-mode network内のTCP疎通であり、Terminal 6物理LANのパケット転送、NAT性能、外部通信の証拠ではない。
- Cホストの管理LAN・SSH・eMMC安定性を優先し、実LANにブリッジせず別の承認済み試験条件で進める。
