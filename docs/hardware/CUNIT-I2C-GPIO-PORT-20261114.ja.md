# C-unit MT6990 I2C and GPIO-key port assessment

Date: 2026-11-14 JST  
Target: SoftBank Air Terminal 6 C-unit, Debian 13 arm64, Linux 6.18.63-debian-t6-proto2.

## Read-only A/C comparison

### Stock A-unit

- The MT6990 controllers at `11ed0000` and `11ed1000` are bound to `i2c-mt65xx`; buses 2 and 3 enumerate clients.
- Bus 2 lists `i2c_lcd_bias` (0x14), `smart_pa` (0x1a), `aw9523b` (0x5b, bound to `aw9523_extern`), and `cap_touch` (0x5d).
- Bus 3 lists `ps5169` (0x28, bound to `ps5169`), `usb_type_c` (0x4e), `direct_charger_1` (0x55), `rt9467` (0x5b), and `buck_boost` (0x75). Another controller lists `msensor`, `alsps`, `gsensor`, and `barometer` clients.
- A's live GPIO debug state has `WPS_KEY` on global GPIO 277, `LEVEL_KEY` on 304, and `RESET_KEY` on 305, each claimed as active-low input by `gpio-keys`.
- A was read-only; no I2C transfers, key presses, LED changes, or output operations were initiated.

### Debian C-unit

- Six MT6990 I2C platform nodes are present, including `11ed0000` and `11ed1000`, but no `i2c-mt65xx` driver is bound and `/sys/bus/i2c/devices` has no adapters or clients.
- The live C nodes expose `compatible = "mediatek,mt6990-i2c"`; the 6.18 driver match table has no MT6990 entry. The kernel config has `CONFIG_I2C_MT65XX=y`, so the blocker is not simply a disabled I2C subsystem.
- C's pinctrl/GPIO subsystem is present (236-line GPIO chip). DT describes WPS/LEVEL/RESET on GPIO 5/28/29. The observed A mapping is GPIO chip offsets 1/28/29 (A's GPIO chip base is 276); C's GPIO5 is currently unclaimed and reported as output. This mismatch makes enabling the existing `gpio-keys` node unsafe until its pin mapping is corrected against board routing.
- C has no input devices, `CONFIG_INPUT_EVDEV` and `CONFIG_KEYBOARD_GPIO` are unset, and only the PCIe `mt76-phy0` LED appears in `/sys/class/leds`.

## Driver source and host build

The public [SBA6D-OSS MT6990 driver source](https://github.com/soralis0912/SBA6D-OSS/blob/c7508cb46a6f51c9873604d6a94c94d5c433a8b6/kernel/src-scrubbed/drivers/i2c/busses/i2c-mt65xx.c) is the full vendor-modified 5.4-era driver, rather than a small compatible-string patch. Its MT6990 support includes a different register map, slave-address register selection, APDMA synchronization/reset sequencing, DMA address width, and transfer timing changes. The source was copied into private build scratch and adapted only for 6.18 API changes (`cpu_latency_qos_*`, `strscpy`, and the void platform-driver remove callback).

The adapted source compiled and linked as an **external AArch64 module** against the C-unit 6.18.63 build tree (`kernelrelease=6.18.63-debian-t6-proto2`). It has not been loaded or installed. A first compile attempt identified the 5.4-to-6.18 API incompatibilities; those were adapted. The later reproducible compile completed with a modpost warning that the description metadata was absent from the resulting object, despite a `MODULE_DESCRIPTION` declaration in the imported source. The `.ko` is a host-only experiment, not a validated replacement for the built-in C driver.

## Safety/result

No I2C driver was bound on C, no bus scan or client transaction was performed, and no GPIO/key/LED output was changed. The candidate module was not loaded: C already has the driver built in, and registering a second copy could conflict; moreover, a host module build alone does not prove safe register behavior. A production C change requires porting the full MT6990 behavior into the exact 6.18 source, rebuilding the signed boot artifact, checking the WPS GPIO mapping, and testing with confirmed recovery access. The existing 5.4 patch is too broad to cherry-pick as a one-line compatible addition.

## Next tests

1. Trace the A and C pinctrl pad numbering and board wiring for the WPS line; do not bind `gpio-keys` while C's GPIO5 mapping is unresolved.
2. Port only the verified MT6990 I2C deltas into the exact C 6.18 driver, compare register maps and transfer paths against the public 5.4 driver, then build the full signed kernel candidate.
3. After a separately approved signature/recovery boot, verify adapter creation and expected clients from sysfs without `i2cdetect`; test one known read-only client operation, then validate AW9523 LEDs only with reversible single-output changes.
4. Enable `KEYBOARD_GPIO` and `INPUT_EVDEV` only after correcting the WPS mapping; observe events without pressing RESET or triggering a vendor action until semantics are documented.

Status: **BLOCKED at safe MT6990 6.18 driver integration and WPS pin mapping**. The A-unit demonstrates several populated I2C clients; C's DT and GPIO chip alone do not prove that the same clients or wiring are operational.
