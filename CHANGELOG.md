# Changelog

## 2026-11-15

- Added an isolated 802.11s kernel config fragment enabling `CONFIG_MAC80211_MESH=y` and source/config validation based on the PR #9 Linux 6.18.63 input.
- Added a host-only two-radio mac80211_hwsim SAE mesh smoke test; peer formation and bidirectional IP passed at 2437 MHz. Multi-hop and C-unit RF behavior remain untested.
- Started an isolated arm64 Image/modules build; no device configuration, RF transmission, or boot partition was changed.
- Recorded that the permitted raspi2 path reached the gateway but C-unit SSH authentication was denied; no alternate host/path was used.

## 2026-11-16

- Re-audited the saved 802.11s ARM64 build inputs. The available stock Linux 6.18.63 tar lacks MT6990 vendor source, while the prior successful private build tree has vendor code but no Git metadata or complete source receipt tying it to the recorded baseline commit.
- Kept the existing Image/module SHA evidence as a host artifact, downgraded the claim of reproducible source provenance, and blocked P25 packaging/device use until the exact vendor source and input manifest are recovered.
- Re-ran mesh config/source validation, project unit tests (2/2), compileall, shell syntax, and the isolated 2-node SAE hwsim bidirectional ping smoke test; no device access or RF transmission occurred.

## 2026-11-14

- Recorded live C-unit Debian 13 hardware inventory, driver/API mapping, Device Tree census, unknown candidates, radio findings and OpenWrt comparison.
- Confirmed ESP32-C3 ESP-AT queries over UART1 with a bounded exclusive query tool; no GPIO reset, firmware update or radio activation command.
- Documented recurring eMMC CQE/write errors, package-file corruption, limited recovery and unresolved persistence risk.
- Added four host-only DT policy candidates and tests, prioritizing removal of supports-cqe. No candidate was flashed or boot-tested.
- Preserved Ethernet/SSH/UART management and prior GitHub evidence. Public artifacts exclude device identifiers, credentials, calibration, raw DTB and vendor firmware.
