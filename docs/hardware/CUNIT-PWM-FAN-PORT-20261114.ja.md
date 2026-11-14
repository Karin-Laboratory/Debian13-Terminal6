# C-unit MT6990 PWM fan port and live test

Date: 2026-11-14 JST  
Target: SoftBank Air Terminal 6 C-unit, Debian 13 arm64, Linux 6.18.63-debian-t6-proto2.

## A/C finding

- C's DT has `pwm@12016000` with `compatible = "mediatek,mt69xx-pwm"`, plus a `pwm-fan` consumer referencing channel 4 at a 10,000 ns period. The PWM controller's provider had no driver, `/sys/class/pwm` was empty, and the fan driver repeatedly deferred with `Could not get PWM` (error 517).
- The 6.18 driver already contains `mt6990_pwm_data`: 7 channels, channel-register base `0x80`, stride `0x40`, and matches `mediatek,mt6990-pwm`. It lacked the vendor DT spelling used by C.
- Stock A binds the same PWM block to `pwm-mediatek` and `pwm-fan`; `pwm1=255` is reported. No fan tachometer channel is exposed on A.
- A separate 6.18 MT6990 patch corroborates the seven-channel register geometry. The vendor 5.4 patch for `mediatek,mt69xx-pwm` lists channel offsets `0x80, 0xc0, 0x100, 0x140, 0x180, 0x1c0, 0x200`, consistent with the 6.18 MT6990 base/stride.

## Change and C-unit test

A minimal source patch adds the C DT compatible alias to the existing MT6990 data. A host-only AArch64 test module was built against the exact 6.18.63 C kernel tree, with a unique platform-driver name so the built-in driver was not replaced or unloaded. The module was staged in `/run` (tmpfs), not on the P44 root filesystem.

After inserting the module:

- `/sys/bus/platform/devices/12016000.pwm/driver` resolved to `pwm-mediatek-cunit-test`.
- `/sys/class/pwm/pwmchip0/npwm` reported 7.
- The deferred `pwm-fan` consumer bound successfully; `/sys/bus/platform/devices/pwm-fan/driver` resolved to `pwm-fan`.
- Its hwmon interface reported `pwm1=255`, `pwm1_enable=1`; the C thermal cooling device appeared with the same zero-state/zero-maximum shape seen on A.
- `/sys/kernel/debug/pwm` identifies channel 4 as `pwm-fan`; requested output was enabled at 9999/10000 ns and the controller reported an enabled 9979/9979 ns waveform after hardware quantization.
- C management remained available: `lan2@eth1` stayed `192.168.3.1/24`, default route stayed via `192.168.3.71`, and SSH, systemd-networkd, serial-getty@ttyS0, and the Wi-Fi PHY service were active.

This verifies controller registration, PWM framework exposure, fan-driver binding and the configured maximum-duty output. There is no tachometer feedback, so physical rotor motion is **not** verified. SoC maximum temperature sampled 65.417°C before and 65.364°C after; the short interval and small change do not demonstrate cooling. No PWM value was manually changed.

## Persistence and safety boundary

The temporary driver remains loaded in RAM for this boot. It is not autoloaded after reboot. No kernel image, DTB, P25/P26 boot region or P44 file was changed. The exact-digest signer accepts a different image hash, so a persistent change still requires the established signing/recovery cycle. The small patch is saved with the feature-ledger PR for that cycle.

To roll back in this boot, unbind `pwm-fan` first, then unbind the test provider and remove the temporary module; this returns to the prior no-provider/deferred-fan state. Reboot also discards the `/run` module and restores the unmodified built-in-driver behavior. If retaining a boot-time fix, apply the alias patch to the signed 6.18 kernel and verify fan behavior/recovery in a separate controlled boot.

Status: **Driver/API verified on C; maximum PWM configuration verified; physical fan rotation and reboot persistence unverified.**
