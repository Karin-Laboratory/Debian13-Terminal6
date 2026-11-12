# Debian 13 Terminal 6: Linux 6.18.63 porting status

As of 2026-11-12 the latest published 6.18.y stable patch release is **6.18.63** (published 2026-11-10, kernel.org).

## Current state: prototype 1 failed physical boot; prototype 2 unsigned candidate built

The C-unit test in private PR #153 (commit `8b32f8d6d000d0c0e0692e73d6070f565cc32d18`)
confirmed full P25 readback, LK certificate verification/decompression and ATF handoff,
followed by watchdog reset before any Linux/initramfs output. Debian and SSH were
not reached. Stock slot B recovered and SSH was confirmed. P26 was unchanged.

The first candidate combined a historically booted RC16 DTB with a vanilla
`tinyconfig` kernel, rather than the retained MT6990 board source/configuration.
The old verifier checked neither printk, ELF/script execution, GIC/timer,
GPT parsing nor MT6990 management LAN driver closure. These are confirmed
manufacturing/verification omissions; the UART silence does not by itself
identify the exact instruction or runtime cause of the watchdog reset.

Prototype 2 source repairs:

- Require early logging, ELF and script execution, GICv3/timer, GPT/eMMC,
  Debian system interfaces and embedded IKCONFIG after Kconfig resolution.
- Preserve the known board configuration and MT6990 drivers during a three-way
  6.18.44-to-6.18.63 stable source upgrade. Conflicts stop the build and are retained.
- Resolve P44 by the unique GPT `PARTNAME=rootfs_data`, independent of MMC numbering.
- Rebuild the C-unit NETSYS/MT7531/path-probe modules against the new kernel,
  embed them with their startup sequence and a BusyBox runtime, and stage a
  transient systemd unit before networkd/SSH. This is experimental, not a LAN PASS.
- Keep exact RC16 template/DTB inputs private. Do not re-sign or flash a new SHA
  without separate owner approval.

Prototype 2 manufacture completed on 2026-11-12 in private build run 43157680253,
using public source commit `56b85307ef8b4b826c1c0172af490e2550a565cf`.
The 32MiB unsigned P25 embeds a 18,962,440-byte ARM64 Image and the 148,765-byte
RC16 DTB. Kernel/module build, required Kconfig checks, board object presence,
module vermagic, independent P25 structure/payload checks and embedded-config
comparison passed. Independent archive inspection confirmed ARM64 BusyBox/modules,
module hashes and service ordering. All 17 source tests and experimental DTS
compilation passed. Private inputs and candidate stay in the owner-private archive.

Stable integration also required the MT6990 PLL device API port, preservation of
stable UART accessor ownership after an auto-merge duplicated UPIO_AU, static
modem/MCU syscore registrations adapted to the data API, and an explicit OF header
for the retained Motorcomm extension. No compiler warning was suppressed to bypass
these errors. Source snapshots initially excluded two required upstream files;
the chosen snapshot plus hash-checked upstream assembler restoration is recorded
in the private manufacturing receipt.

The initial runtime cause remains unconfirmed. The new candidate has not been
signed, flashed or physically booted. Debian, management LAN and SSH are still
unverified on this candidate.

The older sections below are historical records of what was known at each stage,
including statements predating signing and the failed physical test.

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

## Private RC16 manufacturing facts inspected (not copied into public source)

The existing private RC16 manufacturing code at PR #142 uses a boot-v2 producer
inherited from RC13 and requires **a private P25 template, compressed kernel,
bare DTB, initramfs, and an SHA-bound P26**. The actual successful RC16 Image
was reported as 16,543,752 bytes and its gzip payload as 7,440,264 bytes;
the separate bare DTB was 148,765 bytes. These are **historical RC16
measurements**, not build targets or proof that 6.18.63 will work.

For Debian the old P26-SHA-bound initramfs handoff is not directly usable:
root=/dev/mmcblk0p44, ext4 support, initramfs selection, and systemd need a
separate verified path. Neither the private P25 template nor the bare DTB
should be copied to this public repository without an explicit license and
provenance review.

## 2026-11-12 GitHub-only implementation run

New source files:
- `scripts/stage-experimental-dtb.sh`, `scripts/prepare-experimental-dts.py`:
  fetch SHA-pinned independently authored Air6 board DTS and GPL-identified SoC
  source, change only MMC0 status to okay as an **experimental hypothesis**,
  compile and round-trip a DTB. This does not prove clock, power, pinmux, DMA,
  reserved-memory or the eMMC controller.
- `initramfs/init`, `scripts/make-initramfs.sh`: embed minimal static BusyBox
  handoff which attempts P44 ext4 then switches to Debian /sbin/init. Failure
  stays in UART emergency shell. P26 remains untouched.
- `scripts/assemble-template-p25.py`: preserve owner-provided, SHA-pinned,
  known-good **unsigned** LK boot-v2 template header/vendor64 and replace gzip
  kernel/DTB. Ensure the new kernel Image actually embeds the P44 initramfs.
- `scripts/verify-template-p25.py`: independent section, boot-ID, gzip, DTB
  and zero-padded unsigned-tail readback checks.
- `.github/workflows/kernel-integrated.yml`: build Linux 6.18.63 ARM64
  Image with embedded P44 cpio and compiled experimental DTB, ephemerally.
- Unit/source tests run in `source-tests.yml`, DTB compile tests in
  `dtb-test.yml`.

**Do not claim completion solely from CI success.** The public source baseline
does not contain a rights-cleared, boot-verified hardware DTB with correctly
proven MMC power/clock routing. Private RC16 templates and vendor64 bytes are
not automatically redistributable. Public hosted CI has no approved private
boot template and cannot build the target-specific signed-header-compatible P25
bytes from these inputs alone. Reuse of existing unsigned template requires
owner-private, exact-SHA input plus independent readback after manufacture.

Completion requires (a) finished integrated kernel CI; (b) source/hardware
provenance of DTB and required drivers; (c) concrete private template supplied
to controlled offline assembler; (d) actual 32MiB unsigned output with
independent receipt; (e) separately, device boot verification before declaring
the image bootable. No signing, flashing or P44 writes are performed in this work.

## 2026-11-12 actual unsigned P25 built and independently audited

**Private GitHub Actions run:** https://github.com/Karin-Laboratory/SBAT6A-Offline-Archive/actions/runs/43137288343

- Status: SUCCESS, including assembly, independent static readback and private artifact upload.
- Source: this repository at commit `b4d72d3fe9196aa5d3b61e8b4ca1589f233577b9`.
- Input: RC16 owner-private unsigned P25, full SHA-256 `75b723801d99aa43e844c63ab4d4fd2a9415263aa0a33644631bcd2fba928af1`.
- Reused RC16 boot-tested bare DTB: 148,765 bytes, SHA-256 `f9f24ba152d6714626b6c79c205cf190b3875629ef60d73357c769d2d2ea10e3`.
- Debian P44 initramfs SHA-256 `d7da5d14f01524aa0e8f103f3f44fa3cc04e95f9cb3c6c834bb95a657a975518`.
- Linux 6.18.63 uncompressed ARM64 Image 7,528,456 bytes; gzip 3,657,791 bytes.
- **Manufactured unsigned P25:** exactly **33,554,432 bytes**; SHA-256 `3858454916d6f9089d56518110f7331bf0ec4567185389571b7fa885dcc99382`.
- Independent verifier: `UNSIGNED_P25_INDEPENDENT_STRUCTURAL_PASS`.
- Artifact name: `debian13-6.18.63-owner-private-unsigned-p25`, artifact ID `13907489800`; retained owner-private (Actions 7-day retention until 2026-11-19).
- Neither signing nor hardware boot was run. **This is a complete unsigned engineering candidate, not confirmed working or safe-to-flash firmware.**
- The public experimental DTS was built and syntax-tested separately; the actual manufactured candidate uses the exact private RC16 DTB with historical boot success. Linux 6.18.63 runtime compatibility remains unproven.

This closes the **unsigned image manufacture + independent static readback** gate only.

## 2026-11-12 completed owner-private unsigned engineering candidate

An actual **33,554,432-byte** unsigned P25 was assembled in the owner-private
GitHub Actions run `43137288343` from Linux 6.18.63, an embedded P44 Debian
rootfs handoff initramfs, and the SHA-verified historically RC16-used bare DTB
sourced from a private unsigned template.

- Result SHA-256: `3858454916d6f9089d56518110f7331bf0ec4567185389571b7fa885dcc99382`.
- Compiled Image size: 7,528,456 bytes; compressed kernel 3,657,791 bytes.
- Independent unsigned boot-v2 section/header/DTB/kernel/CPIO/zero-tail readback: PASS.
- MediaTek MMC and UART built-in config checks: PASS.
- Private preservation run `43138238641`: PASS; private draft release stores the image and three validation/manifest documents.
- No signing, flashing, hardware boot or Debian rootfs boot test has occurred.

**Important distinction:** the proven RC16 bare DTB bytes remain in the
owner-private pipeline; the published independently drafted DTS/experimental
DTB have not been demonstrated to reproduce those exact bytes or be safe
on hardware. Runtime driver equivalence with the RC16 kernel and the
P44 Debian filesystem are not yet established. This is a finished unsigned
*static engineering candidate*, not a release-ready installable firmware.
