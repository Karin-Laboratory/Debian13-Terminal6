# Changelog

## 2026-11-16

- Added a sanitized, non-mutating C-unit STA verification helper for per-band association/security, gateway ping, DNS, route invariance, link counters, and optional owner-managed iperf3 measurement.
- Added an explicit transient reconnect option guarded by the wired management default route. At the time of the initial helper work, C-unit live Wi-Fi tests were not performed because authorized SSH authentication was unavailable and the UART broker was active.
- Recorded exact next gates for WPA3 STA/AP, reconnect, reboot recovery, and independent AP client validation without overstating existing STA/AP evidence.

## 2026-11-15

- Added C-unit MLO radio inventory and A/C evidence audit. The audit distinguishes driver advertisements and configured APs from a real two-link MLD data session; 6GHz RF remains gated by the exact unit authorization and regulatory DB.
- Fixed the read-only `iw phy` parser to recognize fractional MHz output and added coverage for per-radio inventory, interface-to-wiphy mapping, and missing radio sections. No device or RF operation was performed.

## 2026-11-14

- Recorded live C-unit Debian 13 hardware inventory, driver/API mapping, Device Tree census, unknown candidates, radio findings and OpenWrt comparison.
- Confirmed ESP32-C3 ESP-AT queries over UART1 with a bounded exclusive query tool; no GPIO reset, firmware update or radio activation command.
- Documented recurring eMMC CQE/write errors, package-file corruption, limited recovery and unresolved persistence risk.
- Added four host-only DT policy candidates and tests, prioritizing removal of supports-cqe. No candidate was flashed or boot-tested.
- Preserved Ethernet/SSH/UART management and prior GitHub evidence. Public artifacts exclude device identifiers, credentials, calibration, raw DTB and vendor firmware.
- Added a privacy-filtered, read-only C-unit Wi-Fi runtime snapshot tool with six host unit tests; it never configures a radio or claims regulatory authorization.
- Recorded Debian 13 Wi-Fi 7/6GHz/MLO evidence and limits; cross-built hostapd 2.12 for arm64/nl80211 with EHT support and verified its version under QEMU-user. No device or RF operation was performed.
