# Debian 13 Terminal 6: Linux 6.18.63 porting status

As of 2026-11-12 the latest published 6.18.y stable patch release is **6.18.63** (published 2026-11-10, kernel.org).

## Known inputs

- Public source: [openwrt-terminal-6](https://github.com/Karin-Laboratory/openwrt-terminal-6) provides an upstream Linux v6.18 ARM64 image build workflow and partial MT6990 research drivers.
- Its public board DTS deliberately disables **MMC/eMMC, Ethernet, PCIe and USB** pending hardware validation. That DTS alone cannot boot Debian from P44.
- Reported private RC14/RC16 signed P25 boots and P44 ext4 mounts are historical evidence, **not** complete public, rights-cleared P25 build inputs.

## Delivered in this branch

- ARM64 upstream Linux stable v6.18.63 source build script, building Image and modules with Debian-friendly config options.
- Resolved Kconfig verification and a preliminary unsigned Android boot-v2 header/32MiB-size checker.
- Source-only test workflow, no firmware or build-artifact uploads.

## Still blocking a COMPLETE unsigned P25 image

1. Independently redistributable and boot-validated Terminal 6 DTB/DTS with **eMMC/clock/power/reserved-memory** nodes correctly enabled.
2. LK-compatible P25 layout: proved Android header fields, kernel compression, load addresses, DTB location, allowable signing headroom and full 32MiB padding convention. Generic Android boot.img is not proof of bootability.
3. Port and compile MT6990-specific drivers against **6.18.63**; public donor build evidence is compile-only at earlier 6.18.
4. Build actual kernel bytes and check size, then assemble and independently audit a candidate on a controlled build runner.
5. Test Debian P44 rootfs and stage recovery independently before flashing. Slot B must remain undisturbed.

The provided script **does not** produce a runnable Terminal 6 P25. It is the generic upstream kernel build stage only. No signing or hardware writes are authorized.
