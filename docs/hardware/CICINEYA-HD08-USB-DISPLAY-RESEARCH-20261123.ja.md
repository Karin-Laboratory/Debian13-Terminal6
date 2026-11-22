# CICINEYA HD08 USB-HDMIアダプター解析記録（2026-11-23）

> **目的:** SoftBank Air Terminal 6 の Debian 13 arm64 上で、CICINEYA HD08をUSB接続HDMI出力として利用できるか調査する。現時点ではWindowsと外部agent VMでの観測・静的解析のみ。Debian 13/Terminal 6実機での映像出力は **NOT_TESTED**。
>
> 作業対象をC号機の安定起動基盤から切り離す。P25/slot/ブート制御を書き換えず、当面はユーザー空間で再現・解析する。

## 1. 機材と実測識別

- 製品: CICINEYA HD08（USB Type-A → HDMIアダプター。製品ラベルによるチップ型番は未確定）。
- Windows USBデバイス名: `UDisplay-H8UW`
- USB VID:PID: **`185B:2D1D`**、親複合デバイス `USB\VID_185B&PID_2D1D\UD250530H8UW`
- Windowsで見えた複合インターフェース: `MI_00` USB入力デバイス、`MI_01` USB入力デバイス、`MI_02` `UDisplay-H8UW`、`MI_04` USB大容量記憶装置
- 仮想CD-ROM: `D:`、ボリューム名 `UDisplay`、容量8,132,608 bytes。ファイルは `UDisplay.exe` (7,759,136 bytes; 2025-07-10 16:38) と `autorun.inf` (51 bytes)
- 上記のIDはユーザーのWindows PowerShell `Get-PnpDevice -PresentOnly` と `Get-CimInstance Win32_LogicalDisk` による観測。実チップがActions Micro製であることまでは、この識別情報のみでは断定できない。

## 2. UDisplay.exeの来歴と整合性

- Windowsで計算したSHA-256: `C0AD5096F99B7C88F31C791C818FE5615F1300A1B63087995B4FF6B91CCABEB9`
- PE32 / x86 / GUI executable、FileVersion `2.1.0.1324`、ProductName `UDisplay`、CompanyName `SAGE`
- Windows Authenticode `Status: Valid`。署名主体 `Shenzhen Sage Iot Technology Co., Ltd.`、発行CA `Sectigo Public Code Signing CA EV R36`、証明書期限 2024-03-13～2027-03-14（Windows表示時刻）。
- 署名が有効であることは動作の安全性や実チップ製造者の確定を意味しない。
- 静的解析ファイル: Windows `C:\Users\masat\HD08\UDisplay.exe` → SSH/SCPで `/home/masataka/UDisplay.exe` (agent-101-vm) に転送。
- 解析環境: Debian `agent-101-vm`、venv `~/hd08-venv`、`pefile 2024.8.26`、7-Zip 26.06（Windows）。

## 3. PE内蔵リソースの抽出

7-Zipは `DRV_FILES/38630` の `SETUPAPI.DLL` 構造のみ展開し、全ドライバを取り出せなかった。Python `pefile` の `DIRECTORY_ENTRY_RESOURCE` から `DRV_FILES` 7件を抽出できた。

| Resource ID | バイト数 | `file`判定 / 後続INF照合 |
| --- | ---: | --- |
| 38630 | 82,432 | PE32+ x86_64、Microsoft `SETUPAPI.DLL` |
| 38633 | 12,631 | DER PKCS#7 Signed Data、CAT候補 |
| 38635 | 77,696 | PE32+ x86_64 DLL、INFから `SG_DISP_DRV.dll` 相当と推定 |
| 38636 | 4,236 | UTF-16LE Windows INF、`SG_DISP_DRV.inf` |
| 38637 | 11,379 | DER PKCS#7 Signed Data、CAT候補 |
| 38638 | 30,152 | PE32+ x86_64 native、INFから `SG_DISP_BUS.sys` 相当と推定 |
| 38639 | 2,015 | ASCII Windows INF、`SG_DISP_BUS.inf` |

- 抽出先: `/home/masataka/hd08-drivers/resource-<ID>.bin`
- 38635と38638には取得した版情報がなかった。ファイル名との対応はリソース自体の内部識別およびINF照合が今後必要。
- 38639は **ASCII**。UTF-16LEと誤指定すると文字化けする。確認時は `cat ~/hd08-drivers/resource-38639.bin` を用いる。

### INFに記載されたWindows仮想ディスプレイ構成

`SG_DISP_DRV.inf`:
- `SG_DISP\\BUS` に対するユーザーモードディスプレイドライバ。
- `SG_DISP_DRV.dll`、`UmdfLibraryVersion=2.15.0`、`UmdfExtensions=IddCx0102`。
- `UpperFilters=IndirectKmd`、`WUDFRd`、デバイス名 `Sage Display Manager`。

`SG_DISP_BUS.inf`:
- `Root\\SG_DISP_BUS` のルート列挙仮想バス。
- `SG_DISP_BUS.sys`、`KmdfLibraryVersion=1.15`、サービス名 `SG_DISP_BUS`。
- INFにはUSB `185B:2D1D` との直接マッチが見えず、アプリケーション/別コンポーネントがUSB通信を扱う構成の可能性。

**解釈:** WindowsはIddCxのIndirect Display Driverモデルで仮想画面を生成。USB転送は別途UDisplay側のHID通信関連コードが担当する可能性が高いが、厳密な実行経路は未追跡。

## 4. UDisplay.exe内の静的文字列

`strings -a -n 5 ~/UDisplay.exe` と絞り込みにより、以下を発見。

- H.264エンコード処理のソースパス/クラス名: `CX264Encoder.cpp`、`CIntelEncoder.cpp`、`NVIDIAEncoder.cpp`、`NvEncoderD3D11.cpp`、`CEncoder.cpp`、`NvEncoder::EncodeFrame`、`Encode frame failed`
- Capture: `CD3DCapture.cpp`、`CGDICapture.cpp`、`CCapture.cpp`
- HID: `CHidManager.cpp`、`CHidDevIoImpl`、`HidSend2`、`HidD_GetHidGuid`、`HidP_GetCaps`、`ERROR hid read len:%d`、`ERROR hid write len:%d`
- 独自通信の候補: `CSGUPV3Session.cpp`、`SGLP3.cpp`、`CSGUPV3Session::scheLooper()`、`Got SGLP sync, devId: %d, sn: %s,id: %d:%d, pver: %d, sver: %d, isRsp: %d`
- デバイス関連文字列: `remove "HID\\VID_185B&PID_2D1D&MI_00&Col02"`、`CDeviceManager.cpp`、`CFileChannel.cpp`、`COTAManager.cpp`、`d:\\log\\output.h264`
- ビルドパス `D:\\CI\\PROJECT\\20250710-153810\\libudisplay\\src\\...` がバイナリ内に残存。

**判定:** アプリケーションにはH.264エンコード・HID処理・SGLP関連実装が存在する。しかし「全映像ペイロードがHIDのみを通る」「SGLP3がHD08の映像送信に使用される」「H.264が唯一の形式」といった点は文字列だけでは **UNVERIFIED**。動的USBキャプチャとコード/通信照合が必要。

## 5. 既存OSS調査: USBDisplayStack

- GitHub: https://github.com/IoTSharp/USBDisplayStack
- agentでクローン: `~/USBDisplayStack`。ユーザーが実行した `git clone` 成功を確認。
- 候補実装: `backends/actions-micro/actions_micro_backend.c`
- HIDリプレイ工具: `tools/actions-micro-replay.c`
- ソース定義: `#define ACTIONS_MICRO_VID 0x185b` / `#define ACTIONS_MICRO_PID 0x2d1d`。**今回実測したIDと完全一致**。
- `<linux/hidraw.h>`、`hidraw`探索/照合、Report ID、bootstrap記録の読み込み、送信、heartbeatの周期処理がソースgrepで確認できる。
- `MAX_BOOTSTRAP_REPORTS 16384U`、`DEFAULT_HEARTBEAT_US 1000000ULL` などの定義あり。
- `bootstrap=none|full`、`send_full_bootstrap`、`send_due_heartbeats`、`verify_hidraw`、`open_hidraw` 等の実装箇所をログから確認。

**未確認:** 同一ID以外のハードウェア互換性、ライセンス詳細、映像送信経路の全体、必須キャプチャ/テンプレートの実物、ビルド要件、AArch64ビルド、HD08実機映像出力。既存実装がそのまま動くと断定しない。

## 6. 進捗ゲート

| ゲート | 状態 |
| --- | --- |
| Windows USB識別・仮想CD認識 | PASS |
| UDisplay.exe SHA・Windows署名確認 | PASS |
| PE内蔵ドライバリソース抽出 | PASS |
| Windows INF/IDD/仮想BUS構成の静的解析 | PASS |
| H.264/HID/SGLP関連文字列の取得 | PASS |
| 既存OSS内の同一VID/PID定義の確認 | PASS |
| HD08のLinux接続列挙・HID report descriptor採取 | NOT_TESTED |
| プロトコル初期化の再現 | NOT_TESTED |
| 静止画/動画のHDMI出力 | NOT_TESTED |
| Terminal 6 Debian 13 ARM64での動作 | NOT_TESTED |

## 7. 次回再開手順（まず読み取り専用）

1. `cd ~/USBDisplayStack && git log -1 --format='%H %s'` で解析対象OSSのコミットを固定する。
2. `grep -RniE 'capture|template|replay|experimental|arm64|aarch64' README.md docs | head -100` と `grep -n -A 12 -B 5 'actions-micro' Makefile` で、既存実装の必須データ、制約、依存関係、ビルドの有無を監査する。
3. `actions_micro_backend.c` と `actions-micro-replay.c` を通読し、HID report、bootstrap、heartbeat、H.264フレーム入力の境界と未実装部分を確認する。
4. 必要ならWindowsでUSBPcap等を使い、UDisplay起動から画面出力までのUSB通信を収集する（ファームウェア更新操作は行わない）。ログにUSBシリアルやホスト固有の情報が入る場合は非公開で保管する。
5. 外部Linuxホストで `lsusb -v`、`lsusb -t`、HID descriptor、`/dev/hidraw*` とインターフェース対応を調べる。最初は**read-only**で、ビデオ送信/初期化リプレイはデバイス・ログ照合後に実施する。
6. ARM64へのビルドやUSB通信の評価は、Debian起動安定性と独立させ、P44側ユーザー空間で段階検証する。P25/slot B/ブート制御/既存P44をこの研究のために無断変更しない。

## 8. データ所在と再現性の制約

- Windows原本: `C:\\Users\\masat\\HD08\\UDisplay.exe`（Windows内蔵CD `D:\\UDisplay.exe` コピー）。
- agent原本: `/home/masataka/UDisplay.exe`。抽出物: `/home/masataka/hd08-drivers/`。OSSクローン: `/home/masataka/USBDisplayStack/`。
- このMarkdownは**解析記録のみ**を公開。メーカー配布のEXE、DLL、SYS、INF、CAT原物をGitHubへ複製しない。上記の実機/ファイルは環境変化で消える可能性があるため、SHAとコミットを保存して再現可能性を確認する。
- 現時点で確認できた材料はユーザー提供PowerShell・agentログと既存OSSソースのgrep結果であり、実機USBパケットやLinux上での成功を証明するものではない。
