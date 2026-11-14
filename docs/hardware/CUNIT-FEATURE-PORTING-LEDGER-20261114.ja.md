# C-unit hardware feature porting ledger

Updated: 2026-11-14 JST  
Target: SoftBank Air Terminal 6 C-unit, Debian 13 arm64, Linux 6.18.63-debian-t6-proto2.

This is a measured progress ledger, not a claim of complete hardware support. “Observed” means the named evidence exists; Device Tree presence alone is not proof that a component is populated. Do not infer successful function from driver registration or advertised nl80211 capabilities.

## Status vocabulary

- **Verified operation**: a bounded real-device function test passed.
- **Driver/API**: kernel binding or userspace API observed; function test remains open.
- **Partial**: some function works, or only part of the feature is verified.
- **Blocked**: a known prerequisite or safety gate prevents a valid test.
- **Unknown / candidate**: evidence is insufficient to decide whether hardware is fitted or usable.
- **Not detected**: no device/API was found in the inspected runtime; this does not prove physical absence.

## Current management and safety baseline

On the latest C-unit check after reboot, `lan2@eth1` remained `192.168.3.1/24`; SSH, systemd-networkd, serial-getty@ttyS0, and `terminal6-wifi-phy.service` were active. C-unit IPv4 routing through raspi4 and a previous two-packet ping test succeeded. This preserves the Ethernet/SSH/UART management path.

Global wireless regulatory state was `00`. The 6GHz channels remain disabled; no regulatory override or RF transmission was performed. A’s stock `phy2` 6GHz advertisement and configured 6075 MHz / 320 MHz AP interface are comparison observations only, not proof of lawful C-unit operation. A read-only check found A’s world rules include 5925–7125 MHz / 320 MHz, `NO-OUTDOOR`, 12 dBm, while C’s Debian world rules stop at 5835 MHz. This is a stack/regdb difference, not authorization to import A’s rule.

The current boot’s sampled MMC log showed deferred probes for `11240000.mmc`; no P44 ext4/CQE write-error signature was present in that sample. CQE state was not exposed at the searched sysfs paths after reboot, so its current state is **unverified**. A fresh Wi-Fi log review decoded `Message 0012002d (seq 3) timeout` to `MCU_WM_UNI_CMD(EFUSE_CTRL)`, the command used by `mt7996_mcu_set_eeprom()` to transfer the EEPROM buffer. The initial `mt7996_init_work()` call ignores this function’s return value; PHY registration therefore does not prove the EEPROM buffer reached the MCU. The timeout’s root cause and calibration effect remain unresolved. Prior evidence and the CQE mitigation candidate are recorded in [PR #3](https://github.com/Karin-Laboratory/Debian13-Terminal6/pull/3). No write/throughput stress test was run in this update.

## Feature ledger

| Feature group | C-unit evidence/status | Remaining proof / next concrete step |
|---|---|---|
| Wi-Fi 2.4/5GHz AP and STA | **Partial.** MT7990 endpoints bind to mt7996e/mt7996e_hif; phy0 and nl80211 capability data exist. C-unit Wi-Fi PHY service and phy0 returned after normal reboot. No AP/STA data-plane test in this cycle. | Establish a lawful, isolated 2.4/5GHz AP/STA test with a second client; verify DHCP/IP traffic, counters, and reboot recovery. |
| Wi-Fi 6GHz PHY / channels | **Blocked.** phy0 advertises 6GHz/EHT capability, but global regdomain is `00` and 5925–6415 MHz channels are disabled. A’s stock phy2 is a comparison reference only. | Obtain lawful country/device authorization context; boot the signed initramfs-regdb candidate through the exact approved signature/recovery flow, then re-check regdb load timing and channel state. |
| EHT / 80–320MHz / WPA3-PMF | **Capability only.** No C-unit RF or association test. | First complete lawful 5/6GHz basic AP/STA tests; then independently exercise width, SAE and PMF with supported client. |
| Wi-Fi MLO | **Not verified.** No simultaneous link/counter/traffic evidence from C-unit. A interface configuration is not a C-unit result. | After two-band operation is proven, associate a capable client and capture per-link state, counters and traffic before/after reconnect/reboot. |
| EasyMesh controller/agent | **Not verified on C Debian.** | Port/service compatibility inventory from stock; then isolated controller-agent joining and topology/rejoin tests, separately from MLO. |
| Ethernet / MT7531 / DSA | **Verified bounded operation.** SSH and content-checked transfer were previously observed on LAN2; latest management IP is unchanged. | Map physical jacks to DSA ports; test each fitted external port, VLAN/bridge behavior and hardware-offload counters. |
| WWAN / LTE/5G | **Partial inventory only.** CCCI modem, 21 ccmni interfaces and related control nodes were observed; no SIM registration, PDN, or LTE/NR data session proven. | Compare stock modem daemon/protocol and device state; run a bounded, non-destructive registration/data test only after preserving current control access. |
| GNSS | **Blocked at driver integration.** A has gps_drv/conninfra, GNSS device nodes and gnss/mtk_agpsd services. C has a matching enabled MT6990 DT/resource node but no driver/service. The public GPL v062 driver compiles through object link with a scratch SMC call ID; final module post-processing fails on missing conninfra exports. See [PR #8](https://github.com/Karin-Laboratory/Debian13-Terminal6/pull/8). | Obtain the matching MT6990 conninfra source/API and validate GPS SMC support; complete a clean module build before any device init or location test. Keep stock firmware and location data private. |
| ESP32-C3 UART / AT | **Verified bounded query.** UART1 `/dev/ttyS1`, 115200 8N1 and ESP-AT version/status queries have been observed. | Continue through the bounded Debian BLE/GATT API evidence in [PR #5](https://github.com/Karin-Laboratory/Debian13-Terminal6/pull/5); long-duration and full C reboot recovery remain open. |
| ESP32 BLE / Linux Bluetooth HCI | **Partial / HCI not detected.** ESP-AT BLE APIs and owned-peer GATT operations passed in PR #5. This is proprietary AT control, not a standard Linux HCI controller. | Test arbitrary peripheral/server provisioning, pairing/security UX and reboot/long-run stability; separately investigate HCI feasibility from transport firmware/protocol without claiming HCI support. |
| LEDs / AW9523B / buttons | **Unknown / API absent.** DT descriptions exist, but exterior components and input events have not been mapped. | Read-only stock service/device comparison, then human-assisted physical identification and reversible single-output/input tests. |
| GPIO / pinctrl | **Driver/API observed.** GPIO lines enumerate; no electrical output manipulation or connector mapping in this cycle. | Correlate consumers and board routing before requesting any line; then use safe, reversible tests. |
| I2C / SPI / SPMI / PWM / fan | **Partial inventory; physical population unknown.** DT/controller descriptions exist; I2C adapter enumeration was absent in earlier evidence; no PWM chip/fan proof. | Resolve controller probe/defer, pinmux/clock dependencies; inspect board/stock device bindings before bus scans or output enable. |
| CPU, clocks, power, reset, thermal | **Partial.** Four A55 CPUs, thermal zones, clock/power/reset drivers and watchdog interface observed. No clock/rate, reset, suspend or watchdog firing test. | Compare stock policy and safely test read-only status first; avoid modifying reset/power domains until recovery path is explicit. |
| USB / PCIe / SDIO | **Partial.** PCIe devices and Wi-Fi bind; an additional PCIe probe failure was observed. USB function was not enumerated in prior evidence. | Match each controller/port to actual board population, resolve probe logs and use known-good external devices only. |
| eMMC P44 / ext4 / CQE | **Known risk / partial.** Earlier CQE recovery and ext4 I/O errors exist; later bounded package/IO tests and a normal reboot were recorded in PR #3. This cycle did not write-stress the eMMC and did not independently read the current CQE flag. | Keep logs/build outputs off P44; inspect exact current host state read-only; compare stock and Debian 5.4.238/6.18.63 driver/DT/clock/mode. Do not flash an unsigned kernel. |
| P25/P26 A/B boot and recovery | **Partial.** Candidate structures and prior boot metadata were inspected; this cycle’s P25 candidate is unsigned and unbooted. | Use only a newly authorized exact-digest signing path plus independent verification and confirmed recovery procedure; then conduct a separate controlled boot cycle. |
| RTC / TRNG / crypto / GPU / multimedia | **Unknown or not detected.** Existing inventory finds no active RTC/TRNG/SoC crypto API; shared DT nodes do not prove populated hardware. | Compare stock drivers, services and runtime nodes; classify each as present, not detected, or unproven with evidence. |
| Second independent stock-A sweep | **Not done.** Earlier A/C targeted comparisons are not a fresh device-and-service inventory. | After completing current priority tracks, repeat stock A enumeration independently (devices, services, scripts, interfaces, IRQ/GPIO consumers) and append only new evidence/candidates. |

## Wi-Fi change and validation boundary

The C-unit Wi-Fi startup script now stages the C-unit’s own stock EEPROM bytes under the MT7990 firmware request aliases in volatile `/run`. The original script backup is retained on C-unit. After a normal reboot, the service, aliases, and phy0 were present and management recovered. The driver still logged the generic “eeprom load fail, use default bin” warning; source inspection shows that this warning can precede a successful default-bin request, so it does not establish whether the intended calibration was selected. The later `EFUSE_CTRL` MCU timeout is a separate warning sign that the EEPROM transfer itself may be unconfirmed; identify the firmware/driver compatibility and completion semantics before any Wi-Fi transmit test.

The Debian `regulatory.db` and detached signature were validated and embedded into a rebuilt initramfs in an unsigned P25 candidate. The candidate passed independent structural checks, but exact-digest signing, flashing and boot have **not** been performed. The candidate remains a host-side artifact; see [PR #6](https://github.com/Karin-Laboratory/Debian13-Terminal6/pull/6). Do not promote it to device-ready.

## Reproducible evidence and change history

- [Hardware API inventory and excerpts](CUNIT-INVENTORY-API-20261114.ja.md)
- [DT unknown-device analysis](CUNIT-DT-UNKNOWN-20261114.ja.md)
- [Wi-Fi 7 / 6GHz evidence and candidate](https://github.com/Karin-Laboratory/Debian13-Terminal6/pull/6)
- [eMMC stability and ESP32 baseline](https://github.com/Karin-Laboratory/Debian13-Terminal6/pull/3)
- [ESP32-C3 BLE API and GATT verification](https://github.com/Karin-Laboratory/Debian13-Terminal6/pull/5)
- [C-unit GNSS port assessment](https://github.com/Karin-Laboratory/Debian13-Terminal6/pull/8)

## Outstanding project work

The project is not complete. The immediate critical path is a correctly signed/recoverable regdb-initramfs boot candidate, legal 6GHz operating context, then real 2.4/5/6GHz connectivity and MLO. Parallel independent tracks remain for eMMC CQE root cause, WWAN, GNSS, LED/button mapping, buses and the required second stock-A sweep. No item is marked complete without corresponding device evidence.
