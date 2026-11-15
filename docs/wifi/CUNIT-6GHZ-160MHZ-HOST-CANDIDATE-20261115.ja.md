# C-unit 6 GHz / 160 MHz candidate (host-only)

Date: 2026-11-15

## State

- Kernel patch `patches/0002-mt7996-cunit-6ghz-cap-160mhz-no320.patch` removes the MT7996-family driver's 6 GHz EHT 320 MHz capability advertisement and 320 MHz MCS/NSS and AP MU capability fields. The 80/160 MHz EHT capability fields remain.
- Host module build completed for ARM64 against the staged Linux 6.18.63 source/config, which already contains PR #9’s OTP calibration merge, EFUSE timeout, and EEPROM upload error handling. Thus the host-built module compiles those fixes together with the 320 MHz suppression. `mt7996e-160mhz-no320-hostbuild.ko` is a host build artifact only; it has not been signed, deployed, loaded, or tested on C-unit.
- `hostapd-6ghz-160mhz.example.conf` is a placeholder-only configuration. It uses Japan operating class 134, primary channel 33 (6115 MHz), and center frequency index 47 (6185 MHz), which corresponds to a 160 MHz allocation 6105–6265 MHz. The Japanese MIC technical-conditions report lists 6185 MHz as a permitted 160 MHz center in the lower 6 GHz band; this allocation is within 5925–6425 MHz and within the A775 / 020-240075 certificate's recorded 5955–6415 MHz frequency range.
- The config requires SAE and PMF and encodes AP type 0 (indoor AP/LPI in hostapd 2.12). This is a candidate value only: do not start it until the exact C-unit label/certification and indoor installation are verified.
- No 6 GHz RF transmission has been attempted.

## Verification performed

- ARM64 module compilation: `make -C work/wifi/build/kernel ARCH=arm64 CROSS_COMPILE=aarch64-linux-gnu- M=drivers/net/wireless/mediatek/mt76/mt7996 modules` — PASS; modpost emitted the existing missing `MODULE_DESCRIPTION()` warning.
- Patch source review: 6 GHz 320 MHz width bit, 320 MHz MCS15, NSS320, beamformee/sounding and AP MU 320 capability are not advertised; 160 MHz fields remain.
- Hostapd config values were matched to the staged hostapd 2.12 source's accepted fields and operating-class mapping. No hardware-backed config or RF test has run.

## Gates still open

1. Obtain a permitted management route to raspi4/C-unit; last direct permitted gateway attempt from agent-101-vm returned `No route to host` for raspi2. No C-unit live status was collected in this session.
2. Confirm the physical C-unit product label and exact certification identity/conditions.
3. Sign the existing regdb-containing P25 candidate under the authorized workflow for its exact SHA; independently verify signature/body and candidate-specific recovery/readback.
4. Boot that candidate and prove signed regulatory.db loads at boot and that the effective JP rules permit the selected 160 MHz allocation and power type.
5. Rebuild the complete P25 image from this combined source and the matching PR #9 driver, then sign that exact image and independently verify it. Deployment still requires candidate-specific readback/recovery checks.
6. Confirm the client supports 6 GHz, WPA3-SAE, PMF, EHT and 160 MHz. Then proceed through AP beacon, association, IP traffic, measured link width, and reboot recovery. No 320 MHz operation.

## Sources

- MIC, Information and Communications Council report (6 GHz WLAN): https://public-comment.e-gov.go.jp/pcm/download?seqNo=0000312906
- MIC technology certification search: https://www.tele.soumu.go.jp/j/sys/equ/tech/
- Certificate record A775 / 020-240075 (secondary transcription of the MIC record): https://fccid.io/giteki/020-240075
- Hostapd 2.12 configuration and operating-class implementation are in the staged source accompanying this work.
