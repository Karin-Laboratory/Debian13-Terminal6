# Debian 13 on SoftBank Air Terminal 6

Experimental, community-maintained project to run **Debian 13 (arm64)** on SoftBank Air Terminal 6, reusing publicly redistributable hardware-enablement work from the OpenWrt port.

## Goals

- Boot a minimal Debian 13 arm64 userspace using a device-specific Linux 6.18 LTS kernel.
- Use the existing signed P25 boot path and an ext4 root filesystem on P44, subject to validation.
- Preserve the stock slot B as a recovery path; leave P26 untouched where possible.
- Enable UART, Ethernet, SSH, NFS, and hardware diagnostics to accelerate OpenWrt development.
- Document reproducible builds, tests, known limitations, and recovery prerequisites.

## Status

**Live hardware research on one development unit.** Debian 13 with kernel `6.18.63-debian-t6-proto2` runs from P44 on the C-unit; Ethernet/SSH and ESP32-C3 UART queries have been measured. **eMMC CQE/write I/O errors and rootfs integrity remain unresolved.** This is not a validated general installer or complete hardware-support claim. See the [2026-11-14 hardware report, limitations and mitigation candidates](docs/hardware/README.md). Writing P44 can destroy existing data; preserve recovery before any separate firmware or filesystem work.

## Publication policy

Only publish independently redistributable code and documentation. Do not commit signing secrets, device-specific credentials or calibration data, or proprietary firmware dumps.

## Stock UART / P43-P44 onboarding evidence

Before working on partitions or stock SSH, read [the shared, sanitized stock UART / LK / Emergency Shell field guide](docs/COMMON-STOCK-UART-P43P44-ENTRY.ja.md). It distinguishes demonstrated observations from unverified generic installation steps; it is **not** a completed installer.

## Related work

[OpenWrt port for Terminal 6](https://github.com/Karin-Laboratory/openwrt-terminal-6)
