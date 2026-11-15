# Changelog

## 2026-11-14

- Recorded live C-unit Debian 13 hardware inventory, driver/API mapping, Device Tree census, unknown candidates, radio findings and OpenWrt comparison.
- Confirmed ESP32-C3 ESP-AT queries over UART1 with a bounded exclusive query tool; no GPIO reset, firmware update or radio activation command.
- Documented recurring eMMC CQE/write errors, package-file corruption, limited recovery and unresolved persistence risk.
- Added four host-only DT policy candidates and tests, prioritizing removal of supports-cqe. No candidate was flashed or boot-tested.
- Preserved Ethernet/SSH/UART management and prior GitHub evidence. Public artifacts exclude device identifiers, credentials, calibration, raw DTB and vendor firmware.

## 2026-11-15

- Added a Debian 13 C-unit EasyMesh candidate based on prplMesh 6.0.1 with a local Linux BPL patch for configurable two-radio mappings and fail-closed WPA2/WPA3 security parsing.
- Added read-only interface/control-socket preflight, private runtime platform DB rendering, opt-in systemd service, and a supervisor that avoids upstream network reconfiguration.
- Added synthetic host tests and DUMMY/NL80211 build validation; no A/C live EasyMesh configuration was changed or started.
