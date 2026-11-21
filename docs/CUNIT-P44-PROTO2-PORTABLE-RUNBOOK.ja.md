# Terminal 6 Debian 13: proto2 P44 owner-neutral candidate

**Status (2026-11-21): PRIVATE P44 CANDIDATE ZIP MANUFACTURED, INDEPENDENT READBACK PASS. HARDWARE NOT TESTED; NO PUBLIC BINARY RIGHTS CLEARED.**

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

## Firstboot without a distributed login key or password

The P44 builder incorporates the firstboot code from PR #25. The archive contains no shared user authorized_keys, host private key, root password hash, machine ID, unit serial, MAC or EEPROM/OTP data. At first boot it generates a unique SSH host key.

On a physically isolated PC-to-LAN2 cable ONLY, it temporarily accepts root with no password or user public key at 192.168.1.1:22 using Dropbear -B. ANY other peer on that same link can log in as root. Hardware cannot prove the cable's isolation. NEVER connect this firstboot network to the home LAN/WAN or bridge it through Wi-Fi.

Owner setup:
1. Verify the SSH host key out of band (UART), then ssh root@192.168.1.1.
2. Run passwd root, or register your own root/.ssh/authorized_keys with directory 0700 and file 0600.
3. Run terminal6-p44-firstboot verify-start and from a SECOND authenticated connection to TCP/2223 prove the new password/key. Record the explicit verification marker only from that second session.
4. Run terminal6-p44-firstboot finalize. The service permanently disables firstboot Dropbear, locks the empty root password in key-only mode and enables normal authenticated OpenSSH TCP/22. In rootfs, normal ssh.service is additionally gated by the firstboot-complete marker and disallows empty passwords.
5. Verify passwordless login fails and authorized login works after a separately approved restart. This runtime handshake is NOT_TESTED on this candidate.

If P44 is empty or broken, P25 does not provide an unauthenticated rescue service. Use UART or individually authenticated rescue only.

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
- New firstboot no-password SSH connection, credential switch and reboot persistence: **NOT_TESTED** on device.
- New P44 Wi-Fi PHY, OTP 46 bytes, EEPROM 8/8 ACK and 2.4/5/6 GHz RF: **NOT_TESTED** on device.
- Unit-independent stock filename/board layouts, signed P25 and OEM redistributability: **BLOCKED / NOT_TESTED**.
- P25 writes, P44 writes, slot control, reboot and RF in this workflow: **NOT PERFORMED**.
