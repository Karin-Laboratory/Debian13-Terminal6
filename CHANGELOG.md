# Changelog

## 2026-11-14

- Recorded live C-unit Debian 13 hardware inventory, driver/API mapping, Device Tree census, unknown candidates, radio findings and OpenWrt comparison.
- Confirmed ESP32-C3 ESP-AT queries over UART1 with a bounded exclusive query tool; no GPIO reset, firmware update or radio activation command.
- Documented recurring eMMC CQE/write errors, package-file corruption, limited recovery and unresolved persistence risk.
- Added four host-only DT policy candidates and tests, prioritizing removal of supports-cqe. No candidate was flashed or boot-tested.
- Preserved Ethernet/SSH/UART management and prior GitHub evidence. Public artifacts exclude device identifiers, credentials, calibration, raw DTB and vendor firmware.

- BLE follow-up: owned-peer binary GATT Read/Write, Notify/Indicate, MTU, encrypted-required Read and reconnect verified; independent bounded UART API/CLI and 13 host tests added. ESP custom GATT server and native HCI remain unverified. Restored BLE0/mode2/SYSSTORE1 and gateway radio; stopped unused speederv2-client (not disabled), cause of gateway instability unresolved. Tools staged in /run; no firmware/GPIO changes. Restore process with systemctl start speederv2-client.service. See docs/hardware/CUNIT-ESP32-BLE-20261114.ja.md.

