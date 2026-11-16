# Debian 13 EasyMesh候補のビルド・導入

## 現状

候補は prplMesh 6.0.1 (`5ba21ee04a3b34f0d99635eeacd547d78cb67efe`) のLinux NL80211 BWLである。2026-11-16にDebian 13/arm64向けcross buildとELF/依存関係の静的監査を完了した。C号機への配置・実機起動・IEEE 1905通信は未試験であり、生成物をそのままC号機へ配置しない。

ビルドrunnerはターゲットAMX-prefix内のAmbiorix共有ライブラリを検出し、ビルド出力のprivate `lib/`へコピーする。インストール済みバイナリは`$ORIGIN/../lib`だけをRUNPATHに持つ。installerは実行ファイルと同梱共有ライブラリすべてのELF Machineを検査する。

ローカルパッチ`patches/prplmesh/0001-linux-bpl-configurable-radios-and-secure-security-modes.patch`は、Linux BPLのAP radio index 0/1をprivate platform DBから読み、WPA2-PSK/WPA3-SAE/transition以外の認証値を拒否する。radio/stationの実netdev対応を調べる前にserviceをenableしない。WPA2/WPA3移行モードの設定値は上流パッチと一致する`wpa2-wpa3-psk-sae`のみ受理し、`wpa2-wpa3-transition`は拒否する。APとhostapd制御ソケットは同名、STAの制御ソケットは各radioに一対一で対応させる。supervisorの直接実行でもroot所有のopt-in markerが必要。

## 再現ビルド

必要なもの：prplMeshの固定commit checkout、hostapd 2.12 source layout、Ambiorix依存8ライブラリと`amxo-cg`、CMake、Ninja、libnl、json-c。公開レシピはこれらの入力を検査し、予期しないソース変更があるcheckoutでは停止する。

```sh
packaging/easymesh/build-prplmesh-nl80211.sh \
  <prplMesh-6.0.1-checkout> <hostapd-layout-root> <target-AMX-prefix> <build-dir> [CMake-toolchain-file]
```

Native buildでは`AMX_HOST_PREFIX`を省略でき、target prefixをホスト用コード生成器にも使う。クロスビルドでは、ホスト実行用`amxo-cg`とそのホスト共有ライブラリを持つprefixを`AMX_HOST_PREFIX`に指定し、同じARM64向けAmbiorix共有ライブラリとヘッダーを含むtarget prefixを第3引数へ渡す。これによりホスト実行ツールへtarget ELFをロードしない。`toolchain-debian13-arm64.cmake`は`CUNIT_TARGET_SYSROOT`を必須とし、pkg-config・CMakeの探索をtarget sysrootへ限定する。今回のcross buildはターゲットで実行できないためCTestを省略し、host側14/14とproject 24/24の結果を別枠で記録した。arm64実行とC号機試験が済むまではruntime PASSとしない。

ビルドスクリプトはCMake installを`<build-dir>/stage`へ隔離する。上流が`/etc/acl/admin/prplmesh.json`へprefix外installするため、`DESTDIR`は必須。

```sh
DESTDIR=<isolated-stage> cmake --install <build-dir>
```

service・wrapperのパッケージstageには、CMake prefixとACL policyの両方を渡す。

```sh
DESTDIR=<package-stage> packaging/easymesh/install-easymesh.sh \
  <isolated-stage>/<configured-CMAKE_INSTALL_PREFIX> \
  <isolated-stage>/etc/acl/admin/prplmesh.json <expected-ELF-machine>
```

ELF機種名は`readelf -h`の`Machine`値で指定する（例：開発VMは`Advanced Micro Devices X86-64`、C号機は`AArch64`）。全実行ファイルが一致しなければインストールを拒否する。

このinstallerはファイルを配置するだけで、serviceのenable/start、Wi-Fi設定、bridge/IP/route変更を行わない。

## C号機実機を開始する前の条件

1. arm64向けcross buildまたはC号機上buildを行い、Debian 13/6.18.63のABI・共有ライブラリを確認する。
2. C号機でmanagement IF、2.4/5GHz AP IF、対応するSTA IF、hostapd/wpa_supplicantの実socketをread-onlyで採取する。
3. prplMeshの各無線BSS/STAと既存APの共存・Multi-AP制御互換性を別途検証する。
4. root所有0600のprivate DBとnode設定を生成し、preflightを通す。SSID/PSKを記録・表示しない。
5. C号機上に`ebtables`と必要共有ライブラリを用意する。ebtablesがない場合、serviceはfail closedする。
6. serviceのopt-in markerを明示作成し、A側Controller/Agentに影響を与えない独立peerを用意する。
7. IEEE 1905.1 packet capture、topology、backhaul、実端末association/IPを分けて確認する。

実機に入る前に、管理SSHから復旧できることと既存LAN/無線起動状態を確認する。現在はraspi4認証が通らず、これらの実機条件は満たしていない。
