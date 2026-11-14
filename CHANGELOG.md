# Changelog

## 2026-11-14

- Recorded live C-unit Debian 13 hardware inventory, driver/API mapping, Device Tree census, unknown candidates, radio findings and OpenWrt comparison.
- Confirmed ESP32-C3 ESP-AT queries over UART1 with a bounded exclusive query tool; no GPIO reset, firmware update or radio activation command.
- Documented recurring eMMC CQE/write errors, package-file corruption, limited recovery and unresolved persistence risk.
- Added four host-only DT policy candidates and tests, prioritizing removal of supports-cqe. No candidate was flashed or boot-tested.
- Preserved Ethernet/SSH/UART management and prior GitHub evidence. Public artifacts exclude device identifiers, credentials, calibration, raw DTB and vendor firmware.
- Added a privacy-filtered, read-only C-unit Wi-Fi runtime snapshot tool with six host unit tests; it never configures a radio or claims regulatory authorization.
- Recorded Debian 13 Wi-Fi 7/6GHz/MLO evidence and limits; cross-built hostapd 2.12 for arm64/nl80211 with EHT support and verified its version under QEMU-user. No device or RF operation was performed.
