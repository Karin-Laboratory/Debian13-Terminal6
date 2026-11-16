# Debian 13 P25: public-source input replacement (2026-11-16)

## Goal

Reproduce an **equivalent, functioning** unsigned 32 MiB P25 from independently
obtainable public sources. Byte identity with an old private P25 is **not** a
requirement. Signing is explicitly a separate owner-controlled step.

This PR does **not** claim that goal is complete. It removes one concrete
dependency on an inaccessible private kernel tree: acquisition of selected MT6990
driver sources, bindings, and kernel patches from a pinned public OSS donor.

## Implemented source replacement

- Run `python3 scripts/stage-public-mt6990-sources.py --output /absolute/new-directory`.
- The machine-readable input lock is
  `configs/public-mt6990-sources.json`: 16 known **public text** inputs from
  `13179415360/openwrt-mt6990-lg6851f` revision
  `a40df9a5afb46716dea799acea69f17480df4d82`.
- Source set: core MT6990 clock providers, clock and power bindings, analog
  SGMII PHY, and Linux patches for clock registration, MMC compatibility, SoC
  DTSI, Ethernet support and Lynxi PCS, plus the public MT6990 Android boot-v2 packer. Each source has an exact Git blob
  SHA-1; fetched contents are also written with SHA-256/size to a local receipt.
- Acquisition is UTF-8 text-only, individual-file, size-bounded, allowlisted,
  without a vendor tree checkout or firmware/EEPROM/calibration/signing assets.
  No fetched vendor code is committed to this repository.
- Staging is a reproducible **source input** step, not an automatic patch
  application to the running C-unit kernel. Original copyright/SPDX notices
  must be kept when integrating sources; separate redistribution-rights
  review remains necessary.
- Offline fail-closed tests cover identity mismatch, unsafe paths, duplicate
  inputs, non-text and oversize data, existing destinations and symlink
  ancestors. CI stages and verifies the exact 16 donor blobs temporarily
  without uploading them.


## Template-free unsigned engineering candidate (no private template)

After producing a PUBLIC-source ARM64 Image that embeds exactly one P44
initramfs, and compiling a PUBLIC C-unit board DTB, supply a UTF-8 JSON
boot-v2 profile with the fields required by the upstream public packer:
`cmdline`, `dtb_addr`, `header_size=1660`, `header_version=2`,
`kernel_addr`, `name`, `os_version`, `page_size=2048`,
`ramdisk_addr`, `second_addr`, `tags_addr`.

**Do not borrow LG6851F addresses as C-unit facts.** Determine the Air Terminal
6 fields from non-secret C-unit observations and validate against LK. The
source-built kernel must embed the P44 initramfs, and the raw DTB must have
valid FDT magic and length. Example command with owner-verified public inputs:

```sh
python3 scripts/stage-public-mt6990-sources.py --output /tmp/public-mt6990-new
python3 scripts/assemble-template-free-p25.py \\
  --source-stage /tmp/public-mt6990-new \\
  --profile /path/to/public-cunit-boot-v2-profile.json \\
  --kernel-image /path/to/public-built/Image \\
  --initramfs-cpio-gz /path/to/public-built/initramfs.cpio.gz \\
  --dtb /path/to/public-built/terminal6.dtb \\
  --output /path/to/new-private-unsigned-candidate
```

Result: `p25-unsigned.img` (33,554,432 bytes) and `p25-receipt.json`
marked `UNSIGNED_TEMPLATE_FREE_NOT_LK_VALIDATED`. The producer reuses a
public OSS packer; there is no signed payload, OEM header template or boot
success assertion. The CI-only synthetic P25 trial uses deliberately fake
ARM64/DTB input bytes, not a device firmware. An independent clean kernel
build and C-unit LK/boot/management acceptance are **not yet demonstrated**.

## Verified public reference and standard AOSP DT table

A previous owner-private **read-only** audit against the publicly released
RC16 signed P25 independently established that its 64-byte DTB-section
prefix is a single-entry **Android DT table v0**, not a secret opaque
metadata block. The 32-byte big-endian header and 32-byte entry are
recomputed from the new bare FDT's actual size; board ID/revision/custom
fields are zero. For a 148765-byte FDT the generated 64-byte prefix SHA256
is `f170c43553f75b65bb0f88714f776773f79489cad8725078ddc84bf7fb2d73d2`,
matching the previously validated RC16 observation. For a different FDT
size both table size fields are recomputed: never reuse stale original bytes.

The public release SHA256
`4ee38fb3f85c7980889c5fe08f78a111069b485c9f7b8a13f09913430fa89787`
is independently checked by
`scripts/derive-public-boot-v2-profile.py`. Only non-secret numeric
Android boot-v2 metadata is extracted; Debian's own P44 cmdline replaces
the original. The observed profile is committed under
`configs/public-air6-boot-v2-profile.json`, allowing source builds without
fetching any private P25 template. The published signed image serves as a
**reference measurement**, not an input to the new assembler.

This resolves the 64-byte generation format and numeric Android boot-v2
header provenance. It does not prove the resulting newly composed image
passes all LK checks or boots an Air Terminal 6.

## Public Linux 6.18.63 kernel source replay

`scripts/apply-public-mt6990-kernel.py` applies the pinned public MT6990
SoC, clock and MMC source patch series to a clean stable Linux kernel.
The donor's LG6851F-only hardcoded OCR voltage hunk is explicitly excluded:
it is a separate board's power assumption. No private source or firmware
is needed for these source changes.

[Public core replay Actions run 43792551357](https://github.com/Karin-Laboratory/Debian13-Terminal6/actions/runs/43792551357)
passed on an independently cloned upstream v6.18.63.
The integrated GitHub Actions workflow now attempts compilation of the
actual public MT6990 kernel and construction of a 32 MiB unsigned P25 using
the public experimental board DTB and standard DT table. Its success/failure
must be read from the *actual* run, not inferred from this text. A distinct
network patch replay checks the public MT6990 Ethernet/SGMII PHY/PCS series.

The public experimental board DTS now sets max-frequency=100MHz and does
not enable CQE. It still lacks independent hardware validation of MMC
clock/power routing, DRAM reserved memory and a working NETSYS/SGMII1 path.

## What the owner-private successful build still supplies

1. **Working Air Terminal 6 board DTS/DTB:** the current public board DTS
   deliberately disables eMMC, Ethernet and PCIe; C-unit successful boot used
   an owner-private validated RC16-derived board DTB. Rebuild the minimal
   boot/management DTS from public hardware observations and verify controller
   clocks, pinctrl, power, GIC, reserved memory, Ethernet routing, P44 and
   eMMC 100 MHz/no-CQE. The LG6851F board DTS is not interchangeable.
2. **Other MT6990 board/kernel deltas:** the current private source tree
   contains extra implementation beyond the 16 selected donor inputs.
   Independently stage any further licensed upstream source/patches as needed.
   Existing `scripts/configure-board-kernel.sh` requires an already working
   MT6990 tree. The PR #13 replay currently fails reverse-application of
   the PR #9 wireless patch in four files; do not misclassify this as proven
   identical source.
3. **Boot-v2/header vs acceptance:** the public AOSP DT table is regenerated
   size-correctly and the header addresses are obtained from a SHA-checked
   public RC16 release. Exact LK acceptance of a newly generated source-built
   DTB/kernel and physical P44 boot are still not demonstrated.
4. **P44 rootfs provisioning:** publish a reproducible Debian 13 arm64
   filesystem recipe, matching the initramfs handoff and management services;
   do not copy per-device host keys, credentials or calibration.

## Acceptance chain (distinct outcomes)

`PUBLIC_TEXT_STAGED` -> `KERNEL_SOURCE_REPLAY_PASS` ->
`BOARD_DTB_VALIDATED` -> `UNSIGNED_P25_32M_READBACK_PASS` ->
`SIGNED_BY_OWNER` -> `C_UNIT_BOOT_ETHERNET_SSH_P44_PASS` ->
`INDEPENDENT_PUBLIC_BUILD_PASS`.

The public-source input stage and template-free **synthetic** unsigned P25
assembly are implemented. Actual compatible board kernel/DTB, Air6 boot-v2
profile, independent full source replay and physical boot remain blocked. The others must
remain explicitly BLOCKED/NOT TESTED until supported by real build and physical
measurements. The owner-private success is a reference, **not proof of public
reproduction**.

No OEM signing keys, signing bypass, device write, radio transmission, or
automatic change to C-unit boot slots is performed.
