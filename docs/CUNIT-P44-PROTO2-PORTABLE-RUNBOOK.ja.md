# Terminal 6 Debian 13: proto2 P44 owner-neutral candidate

**Current branch: source candidate; no device acceptance or public binary distribution.** The retained November 21 package listed below is historical, not produced from this branch's current revision or SSH policy.

**Temporary C-unit test sequencing (owner instruction, until BOTH ① loader and ② standalone Debian are complete):** [①/② alternating hardware acceptance policy, owner-private](https://github.com/Karin-Laboratory/Chappie-Memory/blob/main/terminal6/SoftBank-Air6-%E4%BA%8C%E7%B3%BB%E7%B5%B1%E4%BA%A4%E4%BA%92%E5%AE%9F%E6%A9%9F%E8%A9%A6%E9%A8%93%E3%81%AE%E6%9A%AB%E5%AE%9A%E9%81%8B%E7%94%A8%E6%96%B9%E9%87%9D-20261121.md). Hardware tests are exclusive and serial on the C-unit; development/CI can be parallel. On failure, record the first failing gate, exact artifact SHA and UART evidence, restore a known-safe state, and return the defect to the correct workstream. Switch to the other stream only when its candidate is ready and individually authorized. This is not a permanent policy or permission to sign, flash, change slots, reboot or alter P44. Do not confuse proto2 P25/P44 with the separate minimal-loader P25.\n\nGoverning source: design charter v1.4 in docs/architecture/P25-FOUNDATION-POLICY.ja.md. Method B only: manually install using existing Linux commands after a separate, SHA-exact owner authorization. No dedicated installer. No device writes or RF actions are authorized by this source change.

## Fixed P25 boundary

The boot-proven C-unit signed P25 is 33,554,432 bytes and has SHA256
74c1c98b31cdba54f71d16f1983fbeff347bb334c5ae7d7f1353cd57f734936e.
Kernel release: 6.18.63-debian-t6-proto2.

The exact signed P25 is retained in the PRIVATE SBAT6A archive:
https://github.com/Karin-Laboratory/SBAT6A-Offline-Archive/releases/tag/untagged-027373efd2705b1e227c
Asset DEBIAN13-CUNIT-420FF1B8-SIGNED-UNTESTED-p25.img, ID 770875187, GitHub-reported size 33,554,432 bytes, exact SHA as above. The private ARM64 manufacture run [#44859746336](https://github.com/Karin-Laboratory/SBAT6A-Offline-Archive/actions/runs/44859746336) downloaded this asset by ID and independently hashed its complete 32MiB bytes: PASS. No flashing or signing occurred.

PR #25's 6.18.63-t6-public-capable is DIFFERENT. Never mix modules from that build with the boot-proven P25. This SHA is not independent evidence of generic signed P25 redistributability or other-unit boot.

The private, previously hardware-tested three-module Release is:
https://github.com/Karin-Laboratory/Chappie-Memory/releases/tag/terminal6-wifi-success-20261115

- mt76.ko: 26ffb6bd648a8fa91b424bbcf890710f8695d679d45b372e2e7ba05b68449c2f
- mt76-connac-lib.ko: 9f2df583cc73c738f7a186f1ef16faffcb6919bdf915f4ec9cf09a3df1fa05a6
- mt7996e.ko: c87f66f6573d5a4c3d1e829009fc42baf3223f1b0b958c4fc8a549b135e0fecd

The private 3-module Release was downloaded in [Chappie-Memory CI #44858892370](https://github.com/Karin-Laboratory/Chappie-Memory/actions/runs/44858892370), byte-hashed PASS, then transferred privately with a second independent verification in [manufacture CI #44859746336](https://github.com/Karin-Laboratory/SBAT6A-Offline-Archive/actions/runs/44859746336).

The earlier 105-module KVM archive (asset 770074645, SHA256 `442014649e3e384535919fad40e19d2993464f20f1059c77fa4741c017a66abb`) was independently SHA-verified but **does not contain** cfg80211/mac80211. The correct same-release-name 6.18.63-debian-t6-proto2 framework modules were found in historic private Wi-Fi P44 ZIP asset 770849098, SHA256 `3eef462793a97f9f8be14376cd05f96f6acab58049af8495f58360a10a51bdd7`; their vermagic and packaging were independently checked. Source run [#44859147392](https://github.com/Karin-Laboratory/SBAT6A-Offline-Archive/actions/runs/44859147392).

Historical 2026-11-15 hardware result: an earlier installed P44 used per-unit OTP cal-free data (46 bytes on C), uploaded all 8 EEPROM pages and registered a PHY. It does NOT establish that this new candidate boots.

## Portable Wi-Fi initialization

The P44 rootfs blacklists the PCI modalias auto-loader mt7996e, avoiding the measured race where the driver loaded before systemd staged calibration. The systemd unit launches scripts/proto2-wifi-start.sh only on the matching proto2 kernel.

It checks the actual rootfs_data PARTNAME and reads THIS DEVICE's rootfs_a and rootfs_b, mounted read-only. The unit's own 7680-byte MT7990_EEPROM.bin and P26 radio firmware are copied only to tmpfs /run, with size/header and exact firmware-name gates. It then bind-mounts RAM over P44's existing firmware directory without deleting the P44 files. Afterwards it explicitly loads the exact retained mt76 / mt76-connac-lib / mt7996e modules, verifies manifest hashes and checks PHY registration. The successful driver includes local OTP calibration handling and the 30-second MCU timeout.

Other board variants may have different P26/stock formats. Missing files, invalid chip ID, preloaded modules, failed mount or missing calibration must cause Wi-Fi-only FAIL, not shared/default calibration fallback. No radio AP/STA or RF transmission is started. The Ethernet management and SSH units are independent. The shell service does not establish that OTP or all 8 MCU page ACKs succeeded; verify those separately on authorized hardware.

## Current branch SSH status: no remote root enrollment

The current candidate is an offline, fail-closed baseline for LAN validation, not a finished first-boot SSH experience. It provides neither a shared password nor unauthenticated root SSH. The packaged policy requires public-key authentication and denies remote root, password, keyboard-interactive and empty-password authentication. No owner credential is included. On a new image, a TCP or host-key check is not a successful SSH login, and root login rejection is expected.

`terminal6-p44-firstboot check` inspects effective OpenSSH policy only. It does not enroll a user, change credentials or start a service. Do not follow older first-boot setup instructions for this branch. See [the separate Gate 1 acceptance design](hardware/P44-GATE1-ACCEPTANCE.ja.md) for the planned physically activated setup and mandatory password registration before a root shell; that workflow is not implemented here.

## Non-device manufacture and retained candidate receipt

The owner-private Draft Release now contains the exact SHA-reverified candidate ZIP, its relative-path SHA256SUMS and a sanitized machine-readable build receipt:

https://github.com/Karin-Laboratory/SBAT6A-Offline-Archive/releases/tag/untagged-277acdede20c8efeb442

- `P44-install.zip`: **178,516,940 bytes**, SHA256 `9aded7613ffc262060501d633dd2d27600a544b5fd7d35a6bdbeb25ff9b28f09`.
- `SHA256SUMS`: ZIP checksum file with portable relative path, SHA256 `78bb436f69bbaa99285d1edd21c886a25ddd04d889c392b06cd04d5fc40144f6`.
- `BUILD-RECEIPT.json`: sanitized build summary, SHA256 `47eb1b47283b0f1b28bb2c4f0bd3e5b0294ef595c71293d0974011f5e1da42b0`.
- P25 SHA256 fixed to `74c1c98b31cdba54f71d16f1983fbeff347bb334c5ae7d7f1353cd57f734936e`. **No P25 bytes are embedded in P44 ZIP**.
- Exact public source revision used by this ZIP: `36021c563f0b5eb1a618c707b47e65dd2e19b1c1`. Later branch improvements to the private-input fetch helper are not included in that source pin; do not claim this ZIP is identical to the latest branch state.
- Manufacture and independent post-upload full binary readback: [private run #44859746336](https://github.com/Karin-Laboratory/SBAT6A-Offline-Archive/actions/runs/44859746336), SUCCESS.

To manufacture a new (non-device) candidate under Method B on a trusted ARM64 host with private GitHub access:

1. `bash scripts/fetch-proto2-private-baseline.sh /absolute/new-baseline-private-dir` obtains and verifies the signed P25, older 105-module archive for evidence, and historic Wi-Fi P44 ZIP for the actual cfg80211/mac80211 framework module tree. It prints `SIGNED_P25` and `KERNEL_BASE_TREE`.
2. `bash scripts/prepare-proto2-wifi-modules.sh /absolute/new-private-modules-dir /absolute/verified-KERNEL_BASE_TREE` downloads exactly the three private successful MT76 modules, checks SHA and module vermagic, and creates `modules.tar`. An independently SHA-verified private local third argument is supported for approved cross-repository transport.
3. `sudo bash scripts/build-proto2-p44-rootfs.sh /absolute/new-rootfs-dir` creates the owner-neutral Debian13 ARM64 tar archive. Run the owner-identity scanner on it before packaging.
4. As root or with verified read access to the root-owned tar, run `python3 scripts/package-proto2-p44.py --rootfs ROOTFS_TAR_GZ --modules MODULES_TAR --p25 EXACT_SIGNED_P25_IMG --kernel-release KERNEL_RELEASE_FILE --output P44-install.zip --source EXACT_40_HEX_SOURCE_COMMIT`. This refuses mismatched signed P25 SHA, kernel release, module trio hash, missing cfg80211/mac80211 and serialized owner secrets.
5. Independently reopen and SHA-check the ZIP, store privately, download from that saved Release, independently SHA-check and byte-compare before claiming retention PASS.

The private candidate ZIP is a **transport package, not a raw P44 image**, and must not be installed over an occupied P44. No publicly distributable signed P25, OEM binary or universal hardware support has been authorized.

Before initial install, use charter v1.4 Method B and independently prove P44 is EMPTY ext4 (except lost+found). Extract its tar files with root numeric ownership, symlinks, modes, ACLs and xattrs. Never overwrite an existing running P44. For a future C-unit migration, preserve and independently rehash the entire old P44 image, P25, boot-control state, and stock-B/UART recovery route; obtain separate approval for writes and reboot. Never call static tests device PASS.

## Evidence ledger (2026-11-21)

- Historical C-unit P25 boot / wired LAN / SSH / KVM: **HISTORICAL PASS** for existing old P44 only.
- Historical November 15 per-device EEPROM/OTP/PHY and STA links: **HISTORICAL PASS**, not attributable to this manufactured ZIP.
- Downloaded exact signed P25, 105 archive, historic Wi-Fi P44 archive: **SHA PASS** in private CI.
- Three Wi-Fi success modules, same-kernel framework, complete private modules.tar: **SHA / vermagic / packaging PASS**; full kernel internal ABI remains a hardware gate.
- Owner-neutral Debian13 ARM64 rootfs manufactured and scanned for credentials/calibration: **CI PASS**.
- New private P44-install.zip: **MANUFACTURE / INTERNAL SHA / INDEPENDENT PRIVATE RELEASE READBACK PASS**, CI #44859746336.
- Current fail-closed SSH policy: source and build checks are separate from device testing. Password enrollment and reboot persistence: **NOT IMPLEMENTED / NOT TESTED**.
- New P44 Wi-Fi PHY, OTP 46 bytes, EEPROM 8/8 ACK and 2.4/5/6 GHz RF: **NOT_TESTED** on device.
- Unit-independent stock filename/board layouts, signed P25 and OEM redistributability: **BLOCKED / NOT_TESTED**.
- P25 writes, P44 writes, slot control, reboot and RF in this workflow: **NOT PERFORMED**.


## Hardware acceptance addendum — C-unit, 2026-11-21

This hardware run was separately authorized by the owner; it does not broaden the source-change authorization above.

- Exact signed P25 SHA `74c1c98b31cdba54f71d16f1983fbeff347bb334c5ae7d7f1353cd57f734936e` was written only to PARTNAME `boot_a`. Full readback matched. Exact P44 ZIP SHA `9aded7613ffc262060501d633dd2d27600a544b5fd7d35a6bdbeb25ff9b28f09` was installed by Method B after the existing full P44 backup was independently reverified.
- **Debian/P44 boot PASS:** UART observed LK → ATF → Linux/initramfs → P44 `switch_root` → Debian 13. Runtime kernel was `6.18.63-debian-t6-proto2 #2`; root was ext4 RW on `rootfs_data`.
- **eMMC PASS:** HS400, actual clock 94,999,965 Hz, 8-bit, 1.8 V, `cmdq_en=0`; no matching MMC, I/O, or ext4 error in the postboot scan.
- **LAN/SSH PASS:** isolated LAN2 carrier and IP were present; raspi4 ping succeeded 3/3. UART host-key fingerprint was verified out of band. A separate port-2223 public-key session succeeded before firstboot finalization; strict port-22 public-key login then succeeded, unauthenticated access was denied, root password was locked, and firstboot service was inactive.
- **Wi-Fi PHY FAIL at prerequisite:** `terminal6-proto2-wifi.service` stopped at `ROOTFS_A_RO_MOUNT` because P26 (`rootfs_a`) was ext4 `terminal6-config`, not the expected SquashFS. A read-only `ro,noload` inspection found only `lost+found`. No PHY registered; regulatory.db request failed with `-2`. P26 was not changed and no RF transmission occurred.
- **Storage smoke test PASS:** one 16 MiB P44 direct-I/O write/fsync/readback had identical source/readback SHA and was removed after sync; no matching storage errors followed.
- **KVM partial:** `/dev/kvm` and VHE initialization were present; QEMU was absent, so guest regression was NOT_TESTED.
- **Persistence after another reboot NOT_TESTED:** only the separately authorized single A-trial reboot was performed. The A trial was not made permanent. Preboot readback showed B `success=1`; no postboot boot-control writer was used.
- Full UART, partition images, host-key data and device-specific hashes remain in the private evidence area and are intentionally omitted here.

The Debian clock reported an incorrect April date; JST timing used the raspi4 clock. Current status at end of test: slot A Debian/P44 running with authenticated SSH on the isolated management link. P25, boot_b, P26, P43, GPT and stock B were not modified except for the authorized boot_a/P44 operations and finite boot-control selection described above.



## Persistence reboot addendum — owner-approved single restart

After the first finite A trial had successfully reached Debian/P44, the owner separately approved one persistence reboot. The bootloader then reported A retry=4 / success=0 and automatically switched to B. B booted with `bootslot=b`; stock Linux 5.4.238, ping, and strict-key SSH recovered. This is expected finite-trial fallback because A had not been marked successful; it is not a failure of the prior Debian/P44 session.

- boot_a still matched the exact signed candidate SHA. boot_b still matched its preserved pre-write SHA.
- Post-fallback misc was byte-identical to the original stock-B misc snapshot. Only the expected A priority/retry and B priority bytes differed from the post-first-A snapshot; B success remained 1. No software boot-control write was issued.
- In stock B, P44 was mounted only read-only with `ro,noload`, then unmounted. The firstboot completion/auth markers, authorized_keys and SSH host key remained on disk. The host-key fingerprint and authorized-key fingerprint matched their pre-reboot values.
- **On-disk P44 credential persistence: PASS. P44 SSH service runtime after reboot: NOT_TESTED**, because bootloader automatically selected B.
- Current hardware state after this addendum: stock slot B, P44 intact but not mounted, with authenticated B SSH available. The A trial was not made permanent. No further reboot or RF transmission occurred.
- Full UART logs, misc images and device-specific fingerprints remain in private raspi4 evidence; they are not included in this public document.



## Owner-approved persistence retest — 2026-11-21 JST

This addendum supersedes the earlier runtime-persistence `NOT_TESTED` note for the firstboot SSH credentials.

- Starting from verified stock slot B, a finite A trial was reselected with A=(priority 0f, retry 03, success 00, up_type 00) and B=(priority 0e, retry 00, success 01, up_type 00). The full 512KiB misc readback matched the previously verified finite-A image before reboot; B success remained 1.
- UART capture was already active before the single owner-approved reboot. It recorded Preloader B selecting A, `bootslot=a`, A retry 03 / success 00, `DEBIAN13_T6_SWITCH_ROOT_P44`, and the Debian serial login.
- **Post-reboot P44/SSH runtime PASS:** the device returned Debian `6.18.63-debian-t6-proto2`, mounted `rootfs_data` as ext4 read-write root, and accepted strict-host-key-verified public-key SSH from the physically isolated management link. Ping passed 3/3. The authenticated key and host-key fingerprints matched the prior private evidence; firstboot completion/authentication markers remained present, `ssh.service` was active, and the firstboot service was disabled. Root's password state was locked; a no-authentication SSH attempt was rejected.
- eMMC remained at actual 94,999,965 Hz, HS400, 8-bit, 1.8V, CQE disabled. The post-boot MMC/ext4/I/O error scan was empty. The exact signed boot_a P25 SHA remained `74c1c98b31cdba54f71d16f1983fbeff347bb334c5ae7d7f1353cd57f734936e`; boot_b's live SHA matched its preserved backup.
- The post-boot misc image was 524,288 bytes, SHA256 `9119a411b6ca28e05b48a6b4dbba25a1d452cf3ed04d312496748c4f9ea7ee33`, matching the earlier after-A-boot snapshot. A's retry field advanced to 04; A success remained 00 and B success remained 01. A was **not** made permanent. Current state is slot A running as a finite trial; a later restart is expected to fall back to stock B unless boot policy is separately changed.
- Wi-Fi remains **FAIL/BLOCKED** at the known `rootfs_a` SquashFS prerequisite; no PHY registered and no RF transmission occurred. This retest did not rerun the KVM guest or storage write test.
- Raw UART and device-specific evidence remain in the private raspi4 directory `/home/masataka/private/cunit-p44-acceptance-20261121/`; no private logs, keys, or device-specific host-key fingerprints are published. No further reboot or P44/P25/GPT write was performed.


## 2026-11-21: ②新P44受入結果と修正候補（ソースのみ、未実機試験）

- 署名済みproto2 P25 SHA256 74c1c98b31cdba54f71d16f1983fbeff347bb334c5ae7d7f1353cd57f734936e と旧P44 ZIP SHA256 9aded7613ffc262060501d633dd2d27600a544b5fd7d35a6bdbeb25ff9b28f09 でDebian/P44起動、再起動後のLAN2・認証付きSSH・P44永続性はPASS。eMMC実測94,999,965Hz、CQE無効、該当I/Oログなし。A success=0/retry=04、B success=1は未変更。Wi-Fi PHY FAIL、今回のKVMゲストはNOT_TESTED。
- 原因：従来のWi-Fi初期化はP26(rootfs_a)がSquashFSでfirmwareを保持する前提だった。C号機P26は空のext4 terminal6-config。マウント時点で止まり、ドライバ初期化へ到達していない。
- scripts/proto2-wifi-start.sh はC号機自身の純正rootfs_bをROで使用し、そこからEEPROMを取得する。firmwareの完全セットはstock B、実際にSquashFSの個体のみstock A、最後に所有者が個体別・非公開でSHA検証して準備したP44領域の順で試す。どの候補も欠けた場合はWi-FiだけFAIL。個体固有のEEPROM/OTP、OEM firmwareを公開ZIPに入れない。無線送信/AP/STAは開始しない。
- **未確認：** stock Bのfirmwareディレクトリに必要な4ファイルがあるかは現物で未照合。無ければprivate証拠の実ファイル位置とハッシュを採取し、採用済みの同一カーネルMT76モジュールを維持したまま入力源を修正する。PHY、46bytes OTP、EEPROM 8/8 ACKは次回実機で初めて判定する。
- scripts/proto2-slot-a-success.py と terminal6-slot-a-success.service を次期P44 rootfsへ搭載。サービスは**初期状態で無効**。所有者がC号機miscの実書込みを別途承認した後、root所有0600の専用承認マーカーを作成しenableする。デフォルトのスクリプト実行はdry-run。
- 成功書込みゲート：実機slot Aと正確なP25 full SHA、Debian 13/systemd、P44 ext4 rw、LAN2 IP、初回設定完了、認証付きOpenSSH、Wi-Fi service＋PHY＋OTP46bytes＋EEPROM8/8 ACK、MMC/ext4/I/Oエラーなし。全てPASSした場合のみC号機で確認したmisc 512KiB offset 2052のA/B構造を検証し、A retry=0/success=1へ変更。Bのpriority/retry/successなどを不変のまま維持。512KiB全量バックアップ・fsync・readbackを必須とする。
- **未確認とリスク：** このmisc位置はC号機の観測に限定。他個体互換性と停電時のsector書込み原子性は未検証。既知外の値は書込み拒否。ブート成功マークを設定した後の再起動PASSもまだ得ていない。純正Bの復旧資産を保持する。
- **製造境界：** ②では既存の署名済みproto2 P25をバイト固定するので、新たなP25署名は不要。旧P44-install.zipは修正を含まない。次回は新ソースcommit pinでnative arm64 rootfs/ZIPを製造し、内部SHA、モジュールABI、owner-neutral scan、非公開Release保存・独立再取得を完了する。新ZIP SHAが発行されるまでは署名直前・配布完成などと呼ばない。

暫定計画により、C号機実機試験は①と②で排他・原則交互。②の実機PASSを①の共通ローダーP25へ流用しない。署名、P44書込み、slot切替、再起動、RF、misc書込みの承認は別途必要。

## 2026-11-21: Wi-Fi修正版P44のprivate実製造・独立再取得 PASS

前節の「新ZIP未製造」はこの節の記録で更新する。旧候補とは別の製造物。

- P25：実機起動済み署名済み SHA256 74c1c98b31cdba54f71d16f1983fbeff347bb334c5ae7d7f1353cd57f734936e。変更・再署名なし。
- 固定ソースcommit：fcacb9244336807a209b171b34af43cb17678231（PR #41）。
- 公開source/native ARM64 CI：44906293597 SUCCESS。
- private ARM64製造CI：[44906745723](https://github.com/Karin-Laboratory/SBAT6A-Offline-Archive/actions/runs/44906745723) SUCCESS。成功MT76 trioの個別SHAと同一proto2カーネルframework ABI PASS。Debian13 native rootfs製造、owner-neutral scan PASS。
- **新 P44-install.zip：187,389,339 bytes、SHA256 57058163645c0acfe7b9f5f760d7a2dc8af78fca33a81604a8d37d23c5815d3b**。
- Private Draft Release ID 453695494、[保存先](https://github.com/Karin-Laboratory/SBAT6A-Offline-Archive/releases/tag/untagged-bd937c97c022c490c56e)、ZIP asset 775606937。
- SHA256SUMS asset 775606935、SHA256 e1b5ad63c7dae4142dbb6536f4816102e63de7278e2130b8fae73c738a9de2c5。
- BUILD-RECEIPT.json asset 775606939、SHA256 54d77cfe5ffd2e3b422b0e8eec47d43ab4c2a05f6f0691e6d4e6f5843cb2c5e8。
- ZIP CRC/内部manifest確認、private Releaseから独立再ダウンロード、SHA256SUMSの照合、ZIPとreceiptのcmp全バイト一致：PRIVATE_RELEASE_INDEPENDENT_ASSET_READBACK_PASS。
- 旧P44-install.zip（SHA256 9aded7613ffc262060501d633dd2d27600a544b5fd7d35a6bdbeb25ff9b28f09）を上書き・破棄していない。

**未達：** 新ZIPの実機インストール、Wi-Fi PHY、stock B firmware実ファイルの位置、EEPROM 8/8、OTP、RF、misc成功フラグの実機受入はいずれもNOT_TESTED。先代ZIPでのDebian再起動・認証SSH PASSはこの新ZIPの実測ではない。

**境界：** 今回はC号機アクセス、署名、P25/P44/P26/stock B/misc書込み、slot切替、再起動、RFを行っていない。次のC号機受入は①系統と排他調整し、必要な個別承認と現行P44の整合性ある保全後に方式Bで実施する。


## 2026-11-21 owner-authorized acceptance with new P44 candidate — LK-stage FAIL

This entry records the later owner-authorized test of the new Wi-Fi P44 candidate. It supersedes the earlier “not tested” state for this specific ZIP only. It does not change the separate successful results for the previous P44.

- Inputs: signed P25 SHA256 `74c1c98b31cdba54f71d16f1983fbeff347bb334c5ae7d7f1353cd57f734936e` (33,554,432 bytes) and P44-install.zip SHA256 `57058163645c0acfe7b9f5f760d7a2dc8af78fca33a81604a8d37d23c5815d3b` (187,389,339 bytes), source commit `fcacb9244336807a209b171b34af43cb17678231`. Private Release asset ID 775606937 and the signed P25 asset were checked against their exact hashes and the package manifest before use.
- C-unit was confirmed on stock B by UART, with `bootslot=b`; the physical console identified the stock 1.00.10 firmware. P44 was identified as PARTNAME `rootfs_data`, 2,684,321,792 bytes, and unmounted before formatting.
- P44 alone was initialized as ext4 and populated from the package's rootfs and modules tar files using Method B. The installer recorded module verification and clean unmount. A subsequent read-only `e2fsck -fn` completed all five passes with no reported filesystem errors. The rootfs, systemd init, firstboot service and Wi-Fi service files were present.
- During extraction, GNU tar reported POSIX ACL restoration “Operation not supported” under stock-B Linux 5.4.238. The P44 filesystem is clean, but ACL restoration is **NOT_VERIFIED**; verify/repair this metadata using an ACL-capable Debian environment before claiming complete attribute fidelity. Stock-B timestamps also made archive mtimes appear future-dated.
- `boot_a` already matched the exact signed P25 SHA, so it was not rewritten. The stock `quec_bootctrl -s` interface previously source-verified on this C-unit set a finite A trial (A priority 0f/retry 03/success 00; B priority 0e/retry 00/success 01). The readback matched before the single trial reboot.
- UART capture showed Preloader selecting A. The first failure was before Linux: LK's `mrdump_debug_kinfo_fdt_setup` logged `fdt_add_subnode failed offset=0xfffffffe`, then `ASSERT FAILED at platform/mediatek/common/aee/mrdump_setup.c:167` and halted. No Linux, initramfs, P44 mount, or Debian userspace was reached. Watchdog/finite retry handling retried A and then automatically selected B.
- **G1 Debian boot: FAIL at LK/FDT before Linux. G2 Debian LAN/authenticated SSH: NOT_TESTED. G3 Wi-Fi PHY/OTP/EEPROM: NOT_TESTED. G4 Debian storage/restart persistence: NOT_TESTED.** The slot-A success service/authorization marker was not used; A success was not set.
- Final device state was stock B: `bootslot=b`, B `success=1`, ping and strict-key SSH recovered. Boot A still had the exact requested signed P25; boot B remained unchanged. P44 contains the new candidate, is ext4-clean, and is unmounted while B runs. P26, P43, GPT, LK, OEM/NV and calibration were not written.
- UART and install logs, exact device hashes, and detailed state snapshots remain in the private raspi4 evidence directory. No UART raw log, host-key fingerprint, private key, or device-specific identity is included in this public record.

Next work should diagnose the LK FDT/mrdump assertion against the exact boot-proven P25 before any further slot-A reboot. Separately correct or explicitly account for ACL restoration, then obtain fresh authorization before another finite trial if needed.

## 2026-11-22: LK/FDT ASSERT・P44 ACL警告のオフライン原因切分け（実機未操作）

**参照:** [private structural audit CI #44942998796](https://github.com/Karin-Laboratory/SBAT6A-Offline-Archive/actions/runs/44942998796) (SUCCESS), private [sanitized JSON](https://github.com/Karin-Laboratory/SBAT6A-Offline-Archive/blob/research/cunit-lk-fdt-acl-20261122/research/reports/cunit-lk-fdt-acl-20261122.json). 入力はSHA固定の既存C号機署名済みP25 `74c1c98b31cdba54f71d16f1983fbeff347bb334c5ae7d7f1353cd57f734936e` と新P44 ZIP `57058163645c0acfe7b9f5f760d7a2dc8af78fca33a81604a8d37d23c5815d3b`。実機・RF・slot/miscを一切変更していない。

### LKの `fdt_add_subnode` エラーについて

- UARTの `offset=0xfffffffe` は符号付き32-bitでは `-2`。標準libfdtで `-FDT_ERR_EXISTS`、すなわち「同名の子ノードが既に存在するため追加できない」。`-FDT_ERR_NOSPACE` (通常 `-3`) とは異なる。
- P25 32MiBの直接埋込FDTを1個抽出。オフセット `9302080`、148,753 bytes、SHA256 `a6bef90e18c0a16934e6c4196fea60408a1fed08b6ef9b62c7fbe5d7c5632d91`。851 nodes、静的な同名子ノード重複 **0件**。
- P25 FDTには `/mrdump_ext_rst` が存在するが、これがASSERTの直接対象とは証明されていない。**LK実行時の変更後FDTやLK自身の別FDTは今回検査していない**。
- 過去の①ローダーのオフライン検査 [#44909084128](https://github.com/Karin-Laboratory/SBAT6A-Offline-Archive/actions/runs/44909084128) が記録したFDT SHAと同一。既知起動成功P25と今回失敗時のP25はバイト固定で、P44をロードする前にLK ASSERTしたため、Wi-FiやP44 ACLをこのLK停止の直接原因と断定できない。
- **未解明：** C号機のLK mrdump処理が追加する具体的な親・子ノード名、追加処理の順番/多重呼出し、Linux開始前のFDT状態、今回と以前の成功時のLK起動条件差。必ず最初の失敗からのUARTシーケンスと以前の成功ログを並べ、保存済みLKコード／AEE文字列・呼出し系をread-only解析する。推定だけでP25署名、DTB改変やLK書込みをしない。

### POSIX ACL実際の影響と復元

- 新ZIPの `rootfs.tar.gz` (145,289,562 bytes) を全走査。**9,743 tar entries中、ACLを持つのは `./var/log/journal` の1個だけ**。ここに `SCHILY.acl.access`、`SCHILY.acl.default` と対応する2つのPOSIX ACL xattrがある。ほかのファイルのACLメタデータを復元した証拠は不要だが、uid/mode/xattrの完全性は別途保証が必要。
- private ARM64 Linux hostで `setfacl`→`getfacl -n` のprobe PASS。`tar --numeric-owner --acls --xattrs --xattrs-include='*'` でrootfsを**一時ディレクトリに全量展開 PASS**。`/var/log/journal` のaccess/default ACLに GID 4 の `r-x` が存在することを`getfacl -pn`で確認。
- 純正B側の `Operation not supported` はこのACL復元要求に関する警告と整合する。ただしstock Bの ext4 ACL構成・マウント状態は未調査であり、カーネル設定が原因と断定しない。元のP44内容は現在ext4-clean、未マウントで保存されている。
- **次回Debianが起動した後の最小修復案（まだ未実行）:** P44 ext4がrwでACL対応していることを確認してから、`setfacl -m g:4:r-x,d:g:4:r-x /var/log/journal` を実行し、`getfacl -pn /var/log/journal` でaccess/default両方のGID 4を検証。必要ならアーカイブの完全なACLと比較して修正する。Debian側の`acl`コマンド導入・`systemd-tmpfiles`による所有者・モード・ACLの再設定有無も監査する。
- 現時点でP44を再フォーマット・再展開する理由はない。ACLはLK停止の原因でなく、Debian側で後から修復できる可能性が高い。

**試験結果:** 署名済みP25入力SHA・FDT静的検査PASS、ZIP入力SHA・ACL対象の特定PASS、ACL対応Linuxでの復元PASS、private GitHubレポート保存PASS。**C号機でのLK ASSERT根本原因はUNRESOLVED、再起動/PHY/SSHは今回NOT_TESTED。**


## 2026-11-22：② 電源サイクル後のP44 switch_root→PID1失敗（新規第一ブロッカー）

**実機の事実。** C号機に実機起動済みの② signed P25
\`74c1c98b31cdba54f71d16f1983fbeff347bb334c5ae7d7f1353cd57f734936e\`
を①と交互運用中の \`boot_a\` に適用し、C号機・raspi4の32MiB独立読戻し一致後、有限A試験1回だけ実施。
今回は LK/FDT ASSERT **再現せず**、\`pre alloc phandle failed\` 警告後に
Linux \`6.18.63-debian-t6-proto2\` と initramfs へ到達し、
\`DEBIAN13_T6_SWITCH_ROOT_P44\` が出た。その直後に \`/sbin/init\` 実行不能を示す割り込み混在UART出力、
\`Attempted to kill init! exitcode=0x00000100\`、自動B復帰となった。
**最初の未達はP44への引継ぎ/PID1実行**。Debian userspace、LAN2/SSH、Wi-FiはNOT_TESTED。
電源サイクルの因果効果は不明。FDT原因追跡は所有者指示で引き続き \`ON_HOLD / ROOT_CAUSE_UNRESOLVED\`。

- [PR #41実機結果](https://github.com/Karin-Laboratory/Debian13-Terminal6/pull/41#issuecomment-7069277683)
- [意図的P44更新なしの正確な範囲](https://github.com/Karin-Laboratory/Debian13-Terminal6/pull/41#issuecomment-7069306132)
- [非公開Chappie-Memory Draft PR #27](https://github.com/Karin-Laboratory/Chappie-Memory/pull/27)
- raspi4 UART原本：\`/home/masataka/private/cunit-pr41-p25-swap-retest-20261122/\`（原本314094 bytes、SHA256 \`112203da8fac6bcc3f0be0877ea9a4b3b2509699b28d72a8c4ae8724bc417233\`）。生ログ・個体認証情報を公開リポジトリへ複写しない。

**オフラインで確認済みの重要な反証。** 保存済みP44の旧ZIP \`9aded761…f09\` と新ZIP
\`57058163…3b\` を、非公開Releaseから厳密SHA照合して比較したところ、**両方とも**
\`/sbin -> usr/sbin\`、\`/usr/sbin/init -> ../lib/systemd/systemd\`、
実行可能なAArch64 ELF64 \`/usr/lib/systemd/systemd\` と
\`PT_INTERP=/lib/ld-linux-aarch64.so.1\` の実体が揃っている。
[非公開read-only監査のレポート](https://github.com/Karin-Laboratory/SBAT6A-Offline-Archive/blob/research/pr41-switch-root-init-audit-20261122/research/reports/pr41-p44-init-offline-audit-20261122.json)。
**ZIPが正しいことと実機P44の展開後内容が正しいことは別**。
\`e2fsck -fn\` PASSは、個々のファイル・依存ライブラリ・ELF実行可能性の保証ではない。

### 今回のソース修正（実機未適用）

- \`build-proto2-p44-rootfs.sh\`：ネイティブARM64 rootfsを最終tar化する前に
  \`chroot "$out" /usr/lib/systemd/systemd --version\` を実行し、統合/usr symlink・動的ローダ等が壊れたビルドを拒否する。
- \`package-proto2-p44.py\`：実際のrootfs tar内で\`/sbin/init\`までの中間symlink、
  AArch64 ELF64、ELF \`PT_INTERP\` の存在と実行権限を独立確認し、
  欠損ならZIP製造を拒否する。
- \`tests/test_proto2_p44.py\`：正常なsymlink鎖とmissing init/interpreterのnegative fixturesを追加。

この修正は**配布候補の起動前検証強化**であり、既存C号機P44の故障を直した証拠ではない。
署名、再製造された新ZIP、P44再展開、実機書込み、再起動は別ゲート。

### 読み取り専用実機切り分けの結果（2026-11-22）

純正B稼働中のC号機で、PARTNAME `rootfs_data`、2,684,321,792 bytes、ext4を照合した。
起動状態は `bootslot=b`、rootは `/dev/mmcblk0p39`、Linux 5.4.238、B success=1。
厳格な既知host keyによるSSHと隔離管理リンクのpingが成功し、保存済みboot_b SHAも
前回の記録と一致した。P44は開始時未マウントだった。P44を次のコマンドだけで
一時マウントし、調査後にアンマウントした。終了時にmount tableから対象mountが
消えていることを再確認した。

\`mount -t ext4 -o ro,noload /dev/mmcblk0p44 /tmp/cunit-p44-init-ro\`

#### 実機P44のPID 1実行パス

- `/sbin -> usr/sbin`、`/sbin/init -> ../lib/systemd/systemd`。
  よってrootfs内のリンク鎖は `/usr/lib/systemd/systemd` に到達し、リンク先ファイルは
  root:root、mode 0755、133,584 bytes、SHA256
  `46044b7912af7f7087837554b186ca3ddb640c0f6646cf5e625be5078d5db80d`。
- systemdはELF64 little-endian AArch64で、ELF `PT_INTERP` は
  `/lib/ld-linux-aarch64.so.1`。systemd本体と必要な共有ライブラリは実機P44内に存在し、
  読取り時点のP44 mount optionsにも `noexec` はなかった。
- P44の `/lib` はsymlinkではなく実ディレクトリ（root:root、0755）で、
  `/lib/ld-linux-aarch64.so.1` は欠落。一方、実体
  `/usr/lib/aarch64-linux-gnu/ld-linux-aarch64.so.1` は存在し0755、201,344 bytes、
  SHA256 `8839358cf3489b3399256c8ad6daff5147e61023cc3dd584966dfb3eb1928035`。
  `/usr/lib/ld-linux-aarch64.so.1` のsymlink自体も正常。
- `/usr/lib/aarch64-linux-gnu/systemd/` のsystemd依存ライブラリ、libapparmor、
  libselinux、libcは存在し、P44内のリンク・実体を解決できた。
  `/etc/os-release -> ../usr/lib/os-release` も正常で、内容はDebian 13.8。
  systemd本体、`/etc/systemd/system.conf`、`journald.conf`のSHAは下記private証拠に記録。

したがって `/sbin/init` のsymlink自体は正しく、systemdバイナリも存在する。しかし
カーネルがsystemdをexecする際、ELF interpreterとして要求される絶対パス
\`/lib/ld-linux-aarch64.so.1\` がP44 root内で解決できない。この欠落はexec時のENOENTを
直接説明する。systemdのmain自体は起動しておらず、動的ライブラリの実行時ロードにも
到達していない。これは「systemdが起動後に異常終了」ではなく、**PID 1のexec段階で
loaderが見つからず起動失敗した**という判定である。

#### rootfs/modulesアーカイブ差分と原因

保存済みの旧ZIP SHA256 `9aded7613ffc262060501d633dd2d27600a544b5fd7d35a6bdbeb25ff9b28f09` と
新ZIP SHA256 `57058163645c0acfe7b9f5f760d7a2dc8af78fca33a81604a8d37d23c5815d3b` を
asset IDから再取得して検証した。両rootfs tarは正しいmerged-/usr構造
(`lib -> usr/lib`、`usr/lib/ld-linux-aarch64.so.1`、systemd init鎖)を含む。
一方、両modules tarの内容はトップレベル `lib/modules/...`。方式Bの実機deploy scriptは
rootfs tarを先に展開し、その後modules tarを同じP44 rootへ展開する。後者のトップレベル
`lib/` directory entryが先の `lib -> usr/lib` symlinkを実ディレクトリへ置き換え、
modulesだけを残してinterpreterへの `/lib` 経路を隠す。実機で観測した
「`/lib`が実ディレクトリ」「`/lib/ld-linux-aarch64.so.1`欠落」「`/usr/lib`側の
loaderは存在」という組合せは、この展開順・アーカイブ構造と一致する。

**根本原因：P44 package/deployment bug、確度 HIGH / 強く確定。** 署名済みP25の
switch-root実装やsystemdの壊れを示す証拠はない。UART原本SHA256
`112203da8fac6bcc3f0be0877ea9a4b3b2509699b28d72a8c4ae8724bc417233`の出力はCPU間で
interleaveしている。保存原文には `DEBIAN13_T6_SWITCH_ROOT_P44`、init実行失敗の
断片とkernel panic `Attempted to kill init! exitcode=0x00000100` があるが、断片を
連結して完全なエラー行とは扱わない。実際のP25はAndroid boot header上
`ramdisk_size=0`で、gzip展開したkernel Image内にもswitch-root marker/scriptの
可読文字列は見つからなかった。従ってスクリプトの正確な行・呼出し形式は現存の取得物から
未確定だが、実機rootfsのELF interpreter欠落だけで、記録されたPID 1 exec ENOENTを説明できる。

#### 修正と未実機検証事項

\`scripts/prepare-proto2-wifi-modules.sh\`はmodule archiveを
\`usr/lib/modules/...\`として作るよう変更した。
\`scripts/package-proto2-p44.py\`は同じ場所を検証し、トップレベル `lib/`を含む旧形式を拒否する。
GNU tarでrootfsの `lib -> usr/lib` symlinkへ修正版modules archiveを展開する回帰テストを追加し、
loader経路とmodule配置が共存すること、および旧 `lib/modules` layoutの拒否を確認する。
このソース修正は候補ZIPの再製造・署名・実機適用をしていない。現在のP44も変更していない。

private原本・詳細ハッシュはraspi4の
\`/home/masataka/private/cunit-pr41-init-ro-20261122/\` とUART原本保存先に限定する。
P44は調査後にアンマウント済み。C号機はslot Bのまま、再起動・slot切替・書込みなし。
共通LK/FDT ASSERTは本件と独立し、`ON_HOLD / ROOT_CAUSE_UNRESOLVED`。

次の②試験前に、修正版ソースから**新SHAのP44 ZIP**を製造し、そのZIPを独立検証する。
P25は変更しない。新ZIP適用時はまずread-only path checkまたは同等のpackage acceptanceで
`/lib -> usr/lib`と `/lib/ld-linux-aarch64.so.1` の解決を検証する。C号機P44の修復・再展開、
P25署名・実機投入、再起動は別途承認が必要。

本原因の修正はソース・オフラインテストまでであり、実機P44へ適用していない。次回試験は新ZIPの独立製造検証後、別途承認された場合に限る。C号機は純正B稼働のまま安全に引き渡す。
