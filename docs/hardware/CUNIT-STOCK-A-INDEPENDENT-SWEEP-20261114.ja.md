# Independent stock-A / C-unit runtime sweep

Date: 2026-11-14 JST. This is an additional broad read-only sweep. It is **not** the required final second sweep after all known features are ported; that final pass remains open.

## Method

Read-only enumeration of platform devices, `/sys/class` (thermal, hwmon, RTC, watchdog, LEDs, input, GNSS, net, TTY, GPIO), PCI/USB/I2C/SPI/SPMI/MMC bus devices, active process names and A's init-script names. No device scan command, output write, button press, service stop, location acquisition, or secret/package-content read was performed. Client nodes created from DT are treated as candidates unless a driver is bound or a data-path operation is separately verified.

## A-unit fresh observations

- 22 thermal zones were registered, including CPU/GPU/SoC, PMIC, NTC, RF and PA-labelled zones. `rtc0` was backed by `mt6685-rtc`; date/time were readable.
- `pwm-fan` was bound and its hwmon interface reported `pwm1=255`. No tachometer channel was exposed.
- Three input devices were registered: PMIC keys, `mtk-kpd`, and `gpio-keys`. GPIO debug output showed active-low WPS/LEVEL/RESET inputs on global GPIOs 277/304/305, all idle-high.
- Stock LED class exposed 24 labels. No LED was changed or visually asserted.
- Six I2C adapters existed. Several client nodes were instantiated from DT; `aw9523_extern` bound at 2-0x5b and `ps5169` at 3-0x28. Other unbound client names are not treated as proof of physical response.
- Three SPI client nodes, an SPMI bus with PMIC children, MMC `mmc0:0001`, and USB root hubs were enumerated. No USB peripheral was attached in the sampled state.
- Vendor init scripts/daemons included GNSS, `kn_led_controller`, `kn_key_controller`, EasyMesh, modem control, ESP32 UART, Wi-Fi, audio and telemetry-related entries. Only names were captured; no command arguments or user data were collected.
- A's HWRNG sysfs provider had `rng_current=none` and an empty `rng_available`; no active Linux HWRNG API was found.

## C-unit fresh observations and differences

- 13 thermal zones were live; CPU/GPU/SoC and three mt7996 temperature inputs were readable. C has fewer PMIC/RF/PA/NTC sensor zones than A.
- C's PWM provider originally had no driver match and fan was deferred. The volatile MT6990 alias test described in [PWM fan assessment](../pwm-fan-cunit-20261114/assessment.md) now registers the 7-channel provider and fan at maximum duty for this boot. Rotation and cooling remain unverified.
- C has one GPIO controller but no input event devices. A's GPIO-key input offsets correspond to 1/28/29 relative to its GPIO chip; C's DT describes 5/28/29. C GPIO5 is an unclaimed output, while offsets 1/28/29 are unclaimed inputs. We withheld gpio-keys binding due to this discrepancy.
- C has no I2C adapters/clients, no RTC class device, no SPI/SPMI child bus devices, and no USB root hubs. Its platform DT nodes alone do not demonstrate these functions.
- C's `mediatek,trng` node and `CONFIG_HW_RANDOM_MTK=y` do not produce a registered RNG: the driver table lacks the compatible and `/dev/hwrng` read returns `ENODEV`. A also lacked a registered HWRNG provider.
- C continues to expose PCIe MT7990 ports, Ethernet/DSA links, modem virtual interfaces, watchdog, serial ports, and active thermal sensors. The broad process list differs from A's vendor init service set; service migration is not assumed solely from matching process names.

## Follow-up inventory candidates

1. Port the MT6990 I2C implementation before attempting AW9523, PMIC, sensors or button drivers.
2. Correct the C WPS GPIO mapping from verified board routing; enable input/evdev support only through the signed kernel/DT recovery cycle.
3. Compare A's RTC/PMIC SPMI path and additional NTC/PMIC thermal zones against C's unbound or unavailable PMIC interfaces.
4. Determine whether the MT6990 TRNG is MMIO or secure-monitor mediated before adding a match alias.
5. Map physical USB, SPI, LEDs, buttons and fan hardware; sysfs client presence and DT inventory are not sufficient.
6. Repeat this A/C sweep after the known implementation tracks have advanced, then classify every newly observed item in the feature ledger.

Status: **preliminary independent sweep recorded; required final post-port sweep still pending**.
