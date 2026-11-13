# Debian 13 on SoftBank Air Terminal 6

Experimental, community-maintained project to run **Debian 13 (arm64)** on SoftBank Air Terminal 6, reusing publicly redistributable hardware-enablement work from the OpenWrt port.

## Goals

- Boot a minimal Debian 13 arm64 userspace using a device-specific Linux 6.18 LTS kernel.
- Use the existing signed P25 boot path and an ext4 root filesystem on P44, subject to validation.
- Preserve the stock slot B as a recovery path; leave P26 untouched where possible.
- Enable UART, Ethernet, SSH, NFS, and hardware diagnostics to accelerate OpenWrt development.
- Document reproducible builds, tests, known limitations, and recovery prerequisites.

## Status

**Planning / early development.** No Debian boot or hardware support is claimed to be verified yet. Writing P44 can destroy existing OpenWrt overlay data; back up the device and confirm the recovery path before any flashing or repartitioning.

## Publication policy

Only publish independently redistributable code and documentation. Do not commit signing secrets, device-specific credentials or calibration data, or proprietary firmware dumps.

## Stock UART / P43-P44 onboarding evidence

Before working on partitions or stock SSH, read [the shared, sanitized stock UART / LK / Emergency Shell field guide](docs/COMMON-STOCK-UART-P43P44-ENTRY.ja.md). It distinguishes demonstrated observations from unverified generic installation steps; it is **not** a completed installer.

## Related work

[OpenWrt port for Terminal 6](https://github.com/Karin-Laboratory/openwrt-terminal-6)
