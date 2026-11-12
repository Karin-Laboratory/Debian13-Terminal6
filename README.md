# Debian 13 on SoftBank Air Terminal 6

Experimental, community-maintained project to run **Debian 13 (arm64)** on SoftBank Air Terminal 6, reusing publicly redistributable hardware-enablement work from the OpenWrt port.

## Goals

- Boot a minimal Debian 13 arm64 userspace using a device-specific Linux 6.18 LTS kernel.
- Use the existing signed P25 boot path and an ext4 root filesystem on P44, subject to validation.
- Preserve the stock slot B as a recovery path; leave P26 untouched where possible.
- Enable UART, Ethernet, SSH, NFS, and hardware diagnostics to accelerate OpenWrt development.
- Document reproducible builds, tests, known limitations, and recovery prerequisites.

## Status

**Prototype 1 failed its C-unit boot test.** LK verification/decompression and ATF handoff passed, followed by a watchdog reset before Linux output. Debian and SSH have not booted successfully.

Prototype 2 now builds a retained MT6990 board kernel upgraded to Linux 6.18.63, with early UART logging, GPT-name P44 handoff, and same-build management LAN modules. The owner-private unsigned 32MiB P25 passed structural/payload verification and embedded-config comparison. Source tests (17) and experimental DTS compilation pass. Signing and physical retest are pending; static checks do not establish hardware operation. See [porting status](docs/PORTING-STATUS.md).

## Publication policy

Only publish independently redistributable code and documentation. Do not commit signing secrets, device-specific credentials or calibration data, or proprietary firmware dumps.

## Related work

[OpenWrt port for Terminal 6](https://github.com/Karin-Laboratory/openwrt-terminal-6)
