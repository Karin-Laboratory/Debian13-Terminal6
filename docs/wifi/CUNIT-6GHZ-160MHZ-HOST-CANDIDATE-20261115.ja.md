# C-unit 6 GHz / 160 MHz implementation candidate

Date: 2026-11-15

## State

- Kernel patch `patches/0002-mt7996-cunit-6ghz-cap-160mhz-no320.patch` removes the MT7996-family driver's 6 GHz EHT 320 MHz capability advertisement and 320 MHz MCS/NSS and AP MU capability fields. The 80/160 MHz EHT capability fields remain.
- ARM64 module build completed against the staged Linux 6.18.63 source/config, including PR #9’s OTP calibration merge, EFUSE timeout, and EEPROM upload error handling. The `mt7996e-160mhz-no320-hostbuild.ko` artifact was applied to C-unit on 2026-11-16, loaded successfully, and confirmed after a normal reboot. Runtime `iw phy` retains 160 MHz capability and no longer advertises EHT 320 MHz. This is capability/configuration evidence only; no 6 GHz RF transmission or client link was attempted.
- `hostapd-6ghz-160mhz.example.conf` is a placeholder-only configuration. It uses Japan operating class 134, primary channel 33 (6115 MHz), and center frequency index 47 (6185 MHz), which corresponds to a 160 MHz allocation 6105–6265 MHz. The MIC Information and Communications Council public-comment draft for standard-power (SP) operation lists 6185 MHz among lower-band 160 MHz center frequencies. Because that document is a draft for SP, it is only a channel-plan cross-check, not authority for this C-unit LPI device. The selected 160 MHz span is 6105–6265 MHz, inside both the 5925–6425 MHz Japanese low band and the A775 / 020-240075 certificate record’s 5955–6415 MHz frequency interval; the exact C-unit label/certificate and operating conditions remain unverified.
- The config requires SAE and PMF and encodes AP type 0 (indoor AP/LPI in hostapd 2.12). This is a candidate value only: do not start it until the exact C-unit label/certification and indoor installation are verified.
- No 6 GHz RF transmission has been attempted. The 2026 MIC report cited below is explicitly a draft on SP conditions and does not itself clear this device for transmission.
- A regdb-containing, 100 MHz/no-CQE P25 was assembled and signed for exact unsigned SHA256 `f3cf2327287a1c388faa3e8b59cc09bf92bab08cb006cc84912ab2c32b370889`. Protected signer workflow run `43676185512` completed successfully. Independent receipt reports RSA-PSS/certificate-chain verification PASS, unchanged signed body, and output SHA256 `8457ae5b31d38a754442ed0826544e19cf262059d8578b1eb0218d1cc3f2beb8`. Private draft release contains the image and receipt. This P25 retains the 100 MHz/no-CQE DT but does not include the newly built 320 MHz suppression driver; it is only a regdb-boot candidate, not the integrated 160 MHz Wi-Fi image.

## Verification performed

- ARM64 module compilation: `make -C work/wifi/build/kernel ARCH=arm64 CROSS_COMPILE=aarch64-linux-gnu- M=drivers/net/wireless/mediatek/mt76/mt7996 modules` — PASS; modpost emitted a missing `MODULE_DESCRIPTION()` warning. Host module SHA256: `512937107627c2fcd075d8a36cf2573d024f3e3d9da94a741650071f04527990` (artifact not committed).
- C-unit module live load and reboot persistence: PASS. The device copy at `/lib/modules/6.18.63-debian-t6-proto2/updates/terminal6-mt76/mt7996e.ko` has SHA256 `512937107627c2fcd075d8a36cf2573d024f3e3d9da94a741650071f04527990`; enabled `terminal6-wifi-phy.service` accepted the updated `MODULE-SHA256SUMS` and loaded it after reboot. `iw phy` reports 160 MHz capability and no 320 MHz EHT capability. `wlp1s0` remains DOWN.
- Regulatory DB still fails to load (`loaded regulatory.db is malformed or signature is missing/invalid`), global regulatory remains `00`, and no 6 GHz channels are exposed. This driver change does not address the regulatory signature.
- eMMC remained HS400, 8-bit, 1.8 V, actual 94,999,965 Hz, requested 100 MHz, `cmdq_en=0`; the post-reboot log showed all 8 EEPROM pages uploaded and 46 OTP calibration-free bytes merged. No new MMC/CQE/ext4 I/O errors were present.
- ARM64 hostapd v2.12 under QEMU accepted the template through config initialization and failed when QEMU could not connect to generic netlink. No AP/hardware behavior was tested.
- Patch source review: 6 GHz 320 MHz width bit, 320 MHz MCS15, NSS320, beamformee/sounding and AP MU 320 capability are not advertised; 160 MHz fields remain.
- Hostapd config values were matched to the staged hostapd 2.12 source's accepted fields and operating-class mapping. No hardware-backed config or RF test has run.

## Gates still open

1. The first signed regdb P25 (`8457ae5b31d38a754442ed0826544e19cf262059d8578b1eb0218d1cc3f2beb8`) was written to `boot_a`, read back in full with matching SHA256, booted in slot A, and verified after reboot. It did not load regdb because initramfs contained a Debian `benh@debian.org` signature untrusted by this kernel's compiled-in regulatory keys.
2. A replacement unsigned P25 is prepared with the same regulatory.db payload and the upstream `wens` PKCS#7 signature trusted by this kernel. Exact SHA256: `695e88e4de17c673411e8c8b02db1844651558d039c6779ee8b15ffcb83f6208`. It has not been signed, applied, or booted. It requires exact-candidate protected signing and independent verification before the next boot test.
3. Confirm the physical C-unit product label and exact certification identity/conditions before any 6 GHz RF operation.
4. Confirm a client supports 6 GHz, WPA3-SAE, PMF, EHT and 160 MHz. After the regulatory gate is satisfied, proceed through AP beacon, association, IP traffic, measured link width, and reboot recovery. No 320 MHz operation.

## Sources

- MIC, Information and Communications Council public-comment draft for SP 6 GHz WLAN conditions (channel-plan cross-check only): https://public-comment.e-gov.go.jp/pcm/download?seqNo=0000312906
- MIC technology certification search: https://www.tele.soumu.go.jp/j/sys/equ/tech/
- Certificate record A775 / 020-240075 (secondary transcription of the MIC record): https://fccid.io/giteki/020-240075
- Hostapd 2.12 configuration and operating-class implementation are in the staged source accompanying this work.
