# Terminal 6 Debian 13: proto2 P44 owner-neutral candidate

**Status: SOURCE CANDIDATE ONLY. NOT a manufactured ZIP or validated hardware release.**

Governing source: design charter v1.4 in docs/architecture/P25-FOUNDATION-POLICY.ja.md. Method B only: manually install using existing Linux commands after a separate, SHA-exact owner authorization. No dedicated installer. No device writes or RF actions are authorized by this source change.

## Fixed P25 boundary

The boot-proven C-unit signed P25 is 33,554,432 bytes and has SHA256
74c1c98b31cdba54f71d16f1983fbeff347bb334c5ae7d7f1353cd57f734936e.
Kernel release: 6.18.63-debian-t6-proto2.

The exact signed P25 is retained in the PRIVATE SBAT6A archive:
https://github.com/Karin-Laboratory/SBAT6A-Offline-Archive/releases/tag/untagged-027373efd2705b1e227c
Asset DEBIAN13-CUNIT-420FF1B8-SIGNED-UNTESTED-p25.img, ID 770875187, GitHub-reported size 33,554,432 bytes, exact SHA as above. This executor has NOT read/downloaded the actual image bytes. Independently rehash them before any pairing.

PR #25's 6.18.63-t6-public-capable is DIFFERENT. Never mix modules from that build with the boot-proven P25. This SHA is not independent evidence of generic signed P25 redistributability or other-unit boot.

The private, previously hardware-tested three-module Release is:
https://github.com/Karin-Laboratory/Chappie-Memory/releases/tag/terminal6-wifi-success-20261115

- mt76.ko: 26ffb6bd648a8fa91b424bbcf890710f8695d679d45b372e2e7ba05b68449c2f
- mt76-connac-lib.ko: 9f2df583cc73c738f7a186f1ef16faffcb6919bdf915f4ec9cf09a3df1fa05a6
- mt7996e.ko: c87f66f6573d5a4c3d1e829009fc42baf3223f1b0b958c4fc8a549b135e0fecd

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

## Non-device manufacture

0. On a trusted workstation with gh access to BOTH private repositories and zstd installed, run:
   bash scripts/fetch-proto2-private-baseline.sh /absolute/new-baseline-private-dir
   This independently hashes the exact signed P25 and 105-module baseline archive, safely unpacks into a private workspace, and prints the signed image path and the KERNEL_BASE_TREE path. No device action is performed. The archive's actual layout and executable modinfo validation are still required.

1. On a trusted workstation with credentials to the PRIVATE GitHub Release, run:
   bash scripts/prepare-proto2-wifi-modules.sh /absolute/new-private-dir /absolute/KERNEL_BASE_TREE_PRINTED_ABOVE
   This downloads 3 modules and SHA256SUMS, pins hashes/metadata, requires the same-proto2 cfg80211/mac80211 module tree, and creates private modules.tar. The private bytes are not available in this GitHub-only executor; this has NOT been executed here.
2. On an isolated disposable native ARM64 Debian builder with network access/debootstrap, run as root:
   bash scripts/build-proto2-p44-rootfs.sh /absolute/new-rootfs-dir
   This creates a Debian P44 rootfs tar, not a raw partition image. No private firmware or EEPROM is embedded.
3. After independently obtaining a binary signed P25 whose exact size and SHA match the pin, run:
   python3 scripts/package-proto2-p44.py --rootfs ROOTFS_TAR_GZ --modules MODULES_TAR --p25 EXACT_SIGNED_P25_IMG --kernel-release KERNEL_RELEASE_FILE --output P44-install.zip --source EXACT_40_HEX_SOURCE_COMMIT
   The packager refuses any other P25 SHA and module mismatch. It creates a ZIP transport container and never writes a block device.

Before initial install, use charter v1.4 Method B and independently prove P44 is EMPTY ext4 (except lost+found). Extract its tar files with root numeric ownership, symlinks, modes, ACLs and xattrs. Never overwrite an existing running P44. For a future C-unit migration, preserve and independently rehash the entire old P44 image, P25, boot-control state, and stock-B/UART recovery route; obtain separate approval for writes and reboot. Never call static tests device PASS.

## Evidence ledger at authoring

- Historical C-unit proto2 boot / wired LAN / SSH / KVM: PASS for older P44 only.
- Historical private Wi-Fi module SHA / per-unit OTP / 8-page ACK / PHY: PASS for older P44 only.
- Source implementation: DRAFT, host tests and CI require independent verification.
- Downloading actual binary Release assets from this executor: BLOCKED / NOT_TESTED.
- ARM64 rootfs manufacture, actual SHA-verified modules.tar, new ZIP: NOT_TESTED (required builder and signed P25 image unavailable).
- New firstboot handshake, Wi-Fi PHY and OTP on live hardware: NOT_TESTED.
- Different unit EEPROM layout and 6 GHz regulatory/RF: NOT_TESTED or BLOCKED.
- OEM firmware rights, existing signed boot image redistribution and exact per-unit acceptance: BLOCKED pending independent checks.
