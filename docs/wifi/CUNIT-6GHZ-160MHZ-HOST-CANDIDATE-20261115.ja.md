# C-unit 6 GHz / 160 MHz candidate (host-only)

Date: 2026-11-15

## State

- Kernel patch `patches/0002-mt7996-cunit-6ghz-cap-160mhz-no320.patch` removes the MT7996-family driver's 6 GHz EHT 320 MHz capability advertisement and 320 MHz MCS/NSS and AP MU capability fields. The 80/160 MHz EHT capability fields remain.
- Host module build completed for ARM64 against the staged Linux 6.18.63 source/config, which already contains PR #9’s OTP calibration merge, EFUSE timeout, and EEPROM upload error handling. Thus the host-built module compiles those fixes together with the 320 MHz suppression. `mt7996e-160mhz-no320-hostbuild.ko` is a host build artifact only; it has not been signed, deployed, loaded, or tested on C-unit.
- `hostapd-6ghz-160mhz.example.conf` is a placeholder-only configuration. It uses Japan operating class 134, primary channel 33 (6115 MHz), and center frequency index 47 (6185 MHz), which corresponds to a 160 MHz allocation 6105–6265 MHz. The MIC Information and Communications Council public-comment draft for standard-power (SP) operation lists 6185 MHz among lower-band 160 MHz center frequencies. Because that document is a draft for SP, it is only a channel-plan cross-check, not authority for this C-unit LPI device. The selected 160 MHz span is 6105–6265 MHz, inside both the 5925–6425 MHz Japanese low band and the A775 / 020-240075 certificate record’s 5955–6415 MHz frequency interval; the exact C-unit label/certificate and operating conditions remain unverified.
- The config requires SAE and PMF and encodes AP type 0 (indoor AP/LPI in hostapd 2.12). This is a candidate value only: do not start it until the exact C-unit label/certification and indoor installation are verified.
- No 6 GHz RF transmission has been attempted. The 2026 MIC report cited below is explicitly a draft on SP conditions and does not itself clear this device for transmission.
- A regdb-containing, 100 MHz/no-CQE P25 was assembled and signed for exact unsigned SHA256 `f3cf2327287a1c388faa3e8b59cc09bf92bab08cb006cc84912ab2c32b370889`. Protected signer workflow run `43676185512` completed successfully. Independent receipt reports RSA-PSS/certificate-chain verification PASS, unchanged signed body, and output SHA256 `8457ae5b31d38a754442ed0826544e19cf262059d8578b1eb0218d1cc3f2beb8`. Private draft release contains the image and receipt. This P25 retains the 100 MHz/no-CQE DT but does not include the newly built 320 MHz suppression driver; it is only a regdb-boot candidate, not the integrated 160 MHz Wi-Fi image.

## Verification performed

- ARM64 module compilation: `make -C work/wifi/build/kernel ARCH=arm64 CROSS_COMPILE=aarch64-linux-gnu- M=drivers/net/wireless/mediatek/mt76/mt7996 modules` — PASS; modpost emitted a missing `MODULE_DESCRIPTION()` warning. Host module SHA256: `512937107627c2fcd075d8a36cf2573d024f3e3d9da94a741650071f04527990` (artifact not committed).
- ARM64 hostapd v2.12 under QEMU accepted the template through config initialization and failed when QEMU could not connect to generic netlink. No AP/hardware behavior was tested.
- Patch source review: 6 GHz 320 MHz width bit, 320 MHz MCS15, NSS320, beamformee/sounding and AP MU 320 capability are not advertised; 160 MHz fields remain.
- Hostapd config values were matched to the staged hostapd 2.12 source's accepted fields and operating-class mapping. No hardware-backed config or RF test has run.

## Gates still open

1. Obtain a permitted management route to raspi2; the latest allowed attempt from agent-101-vm returned `No route to host`. No C-unit live status was collected in this session.
2. Confirm the physical C-unit product label and exact certification identity/conditions.
3. From an approved management host, apply the signed regdb P25 using the documented slot recovery path, verify the exact target and full readback SHA, then boot it and prove the signed regulatory.db loads and record effective rules/channels. Signing and prior slot-B recovery history do not constitute a test of this candidate's write/readback/boot.
4. Rebuild the complete P25 image from this combined source and the matching PR #9 driver, then authorize/sign that exact integrated image and independently verify it. Deployment still requires candidate-specific readback/recovery checks.
5. Confirm the client supports 6 GHz, WPA3-SAE, PMF, EHT and 160 MHz. Then proceed through AP beacon, association, IP traffic, measured link width, and reboot recovery. No 320 MHz operation.

## Sources

- MIC, Information and Communications Council public-comment draft for SP 6 GHz WLAN conditions (channel-plan cross-check only): https://public-comment.e-gov.go.jp/pcm/download?seqNo=0000312906
- MIC technology certification search: https://www.tele.soumu.go.jp/j/sys/equ/tech/
- Certificate record A775 / 020-240075 (secondary transcription of the MIC record): https://fccid.io/giteki/020-240075
- Hostapd 2.12 configuration and operating-class implementation are in the staged source accompanying this work.
