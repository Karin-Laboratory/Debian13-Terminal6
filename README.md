# Debian 13 on SoftBank Air Terminal 6

Experimental, community-maintained project to run **Debian 13 (arm64)** on SoftBank Air Terminal 6, reusing publicly redistributable hardware-enablement work from the OpenWrt port.

## Goals

- Boot a minimal Debian 13 arm64 userspace using a device-specific Linux 6.18 LTS kernel.
- Use the existing signed P25 boot path and an ext4 root filesystem on P44, subject to validation.
- Preserve the stock slot B as a recovery path; leave P26 untouched where possible.
- Enable UART, Ethernet, SSH, NFS, and hardware diagnostics to accelerate OpenWrt development.
- Document reproducible builds, tests, known limitations, and recovery prerequisites.

## P25 foundation architecture / Codex guidance

**Architecture source of truth:** [P25 stable-foundation design charter (Japanese)](docs/architecture/P25-FOUNDATION-POLICY.ja.md). It defines the separation of P25 boot/kernel/initramfs and P44 Debian/modules, management and recovery requirements, ABI/Device Tree limits, reproducible upgrades and decision controls. **It is a policy, not evidence that any candidate has passed a physical boot test.**

**For Codex and other repository agents:** start with [AGENTS.md](AGENTS.md), then read the current design charter and the relevant PR/runbook before changing implementation. Architecture changes require an explicit owner-approved proposal; experiment outcomes are recorded separately.

**First-boot setup decision (2026-11-18; revised for Method B):** the owner selected OpenWrt-style **unauthenticated root SSH only on a physically isolated wired LAN** at `192.168.1.1`. The first SSH login occurs in **Debian already installed on P44**, *not* in a P25/initramfs installer. The user then sets a device-specific root password or SSH public key, after which unauthenticated access must be disabled. If P44 is empty or invalid, Debian and its unauthenticated setup SSH **must not start**; use UART and authenticated recovery instead. This is a **design decision, not an implemented or hardware-validated release**. See [first-boot SSH decision (Japanese)](docs/architecture/decisions/CUNIT-FIRSTBOOT-SSH-OPENWRT-STYLE-20261118.ja.md).

**Debian paired-release preparation (2026-11-18; Method B, manual/Codex):** publish a compatible pair of a signed P25 boot image and `P44-install.zip`. **No dedicated external or initramfs installer will be built.** Before booting Debian slot A, the owner-authorized Codex agent or a human, using standard Linux commands in stock B or a verified recovery environment, writes the signed P25 to the confirmed `boot_a` partition (e.g. `dd`) and extracts the verified Debian rootfs tar plus matching modules into mounted P44 ext4 while preserving Linux metadata. The ZIP is only a transport container, **not a raw P44 image**. Follow a documented, checked sequence including PARTNAME, backups, hashes, and readback; never overwrite occupied P44 or host keys without explicit approval. This is a **design and work-process decision, not hardware-validated installation**, and signed-image redistribution/boot conditions remain independently gated. See [charter v1.4 §8A](docs/architecture/P25-FOUNDATION-POLICY.ja.md) and [Method B ADR](docs/architecture/decisions/CUNIT-EXTERNAL-P44-INSTALL-METHOD-B-20261118.ja.md).

## Status

**Live hardware research on one development unit.** Debian 13 with kernel `6.18.63-debian-t6-proto2` runs from P44 on the C-unit; Ethernet/SSH and ESP32-C3 UART queries have been measured. **eMMC CQE/write I/O errors and rootfs integrity remain unresolved.** This is not a validated general installer or complete hardware-support claim. See the [2026-11-14 hardware report, limitations and mitigation candidates](docs/hardware/README.md). Writing P44 can destroy existing data; preserve recovery before any separate firmware or filesystem work.

## Publication policy

Only publish independently redistributable code and documentation. Do not commit signing secrets, device-specific credentials or calibration data, or proprietary firmware dumps.

## Stock UART / P43-P44 onboarding evidence

Before working on partitions or stock SSH, start with [the shared OpenWrt/Debian initial preparation guide](https://github.com/Karin-Laboratory/openwrt-terminal-6/blob/main/START-HERE.ja.md) and [its publication boundaries](https://github.com/Karin-Laboratory/openwrt-terminal-6/blob/main/docs/COMMON-INITIAL-PREPARATION-PUBLICATION.ja.md). The [Debian-facing index of shared UART / LK / Emergency Shell evidence](docs/COMMON-STOCK-UART-P43P44-ENTRY.ja.md) provides the related field guide. It distinguishes demonstrated observations from unverified generic installation steps; it is **not** a completed installer.

## Wi-Fi 7 / 320 MHz test-mode policy

The C-unit retains 160 MHz as the ordinary 6 GHz EHT capability ceiling. A separate, future **SSH-selected anechoic-chamber test mode** is proposed to make 320 MHz driver capability available **without enabling RF transmission until independent legal and test-facility gates have passed**. This mode and its SSH commands are **not implemented**. See [C-unit 320 MHz chamber-mode policy (Japanese)](docs/wifi/CUNIT-320MHZ-CHAMBER-MODE-POLICY-20261116.ja.md).

## Related work

[OpenWrt port for Terminal 6](https://github.com/Karin-Laboratory/openwrt-terminal-6)
