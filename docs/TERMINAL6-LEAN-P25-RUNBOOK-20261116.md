# Terminal6-lean public P25: build / acceptance runbook

State: **DRAFT / offline development**. Sign, physical LK boot, P44 LAN,
Wi-Fi PHY and real SSH are NOT TESTED for this new candidate.

## Scope and evidence inherited

- Public-source parent [PR #14](https://github.com/Karin-Laboratory/Debian13-Terminal6/pull/14).
- Public source-only core build [CI #43809011897](https://github.com/Karin-Laboratory/Debian13-Terminal6/actions/runs/43809011897):
  32 MiB unsigned P25 SHA256
  `4a456cfaeb3dfe357ad26325b879ddceabfd9e873c72cdbe16d7716de2d5d8f3`,
  independent readback PASS but **Image 50,993,664 bytes**.
- The C-unit owner reported that a ~48.6 MiB uncompressed Image is known
  **not to boot**. The earlier private signer gates this size below 35 MiB.
- Public NETSYS source replay [CI #43811851541](https://github.com/Karin-Laboratory/Debian13-Terminal6/actions/runs/43811851541) PASS,
  but cannot prove the experimental public Ethernet DTB's hardware wiring.
- Existing working private C-unit kernel/P44/management records are **reference
  evidence, not evidence that this public kernel boots**.

## Lean profile design and limits

`KERNEL_PROFILE=terminal6-lean` selects an explicit ARM64 tinyconfig-derived
source and requests:

- Arm64 4 KiB page / 39-bit virtual-address geometry, SMP and MT6990 clock,
  interrupt timer, pinctrl and regulators.
- Built-in 8250/MT6577 UART, earlycon, eMMC/MMC, GPT, ext4, devtmpfs,
  gzip initramfs, P44 userspace handoff.
- Built-in NETSYS, SGMII PHY/PCS and MT7531 DSA, network bridge and Debian
  systemd/SSH primitives.
- OverlayFS, TUN, veth and loop as same-build modules, packaged separately
  from the unsigned P25.

The actual resolved Kconfig, not the script's feature requests, is checked by
`scripts/verify-kconfig.py --terminal6 --lean`. Missing builtins/modules or
wrong 39-bit VA terminate the build. The code also rejects an uncompressed
Image exceeding 33,554,432 bytes; this is stricter than the **existing** 35MiB
protected signer and is not evidence that LK accepts the resulting Image.

The new public kernel currently **does not claim MT7990 Wi-Fi PHY support**.
Any follow-up modules and proprietary firmware/calibration must be audited in
the separate Wi-Fi migration lane, with no unauthorized RF transmissions.

## Replay in an isolated ARM64 host

Run only on a disposable native ARM64 host with Git, compiler, libssl-dev,
libelf-dev, flex, bison, device-tree-compiler, busybox-static, cpio:

```sh
python3 -m unittest discover -s tests -p 'test_terminal6_lean_config.py' -v
bash scripts/make-initramfs.sh /bin/busybox /absolute/fresh/initramfs.cpio.gz
bash scripts/stage-experimental-dtb.sh /absolute/fresh/dtb
python3 scripts/stage-public-mt6990-sources.py --output /absolute/fresh/stage

KERNEL_PROFILE=terminal6-lean PUBLIC_MT6990_SCOPE=network \
PUBLIC_MT6990_STAGE=/absolute/fresh/stage \
INITRAMFS_ARCHIVE=/absolute/fresh/initramfs.cpio.gz \
DTB_PATH=/absolute/fresh/dtb/board/terminal6-debian-ethernet-experimental.dtb \
WORKDIR=/absolute/fresh/linux JOBS=4 \
  bash scripts/build-linux-6.18.sh
```

All output paths must be new. On PASS, the Image and Image.gz, resolved
kernel.config, hashes, section sizes, and same-build kernel modules tar
are under the selected `WORKDIR/output`. Construct P25 with the existing
`scripts/assemble-template-free-p25.py` and independently verify with
`scripts/verify-public-unsigned-p25.py`, as executed by
[dedicated CI #43880739533](https://github.com/Karin-Laboratory/Debian13-Terminal6/actions/runs/43880739533).
Never copy the now-failed baseline P25 as a manufacturing input.

The public workflow emits only hashes and measured values, never an
unsigned binary artifact. Preserve an exact new candidate only in a
separate authorized private owner-only build/output lane with matching
full-byte SHA and receipt.

## Acceptance gates

1. **LEAN_CONFIG_PASS**: real Linux 6.18.63 `.config` passes
   builtin + module + VA39 check.
2. **IMAGE_SIZE_PASS**: Linux Image is actually <= 32 MiB uncompressed;
   capture exact bytes and SHA.
3. **P25_32M_READBACK_PASS**: actual 33,554,432-byte unsigned P25 built
   from the new Image; independent boot-v2/gzip/AOSP DT/initramfs/SHA checks.
4. **PRIVATE_RETENTION_PASS**: new SHA fixed and artifact/receipt preserved
   privately with readback; no public binary.
5. **OWNER_SIGNING_NEW_SHA**: STOP, request new explicit SHA-specific approval.
6. **C_UNIT_LK/BOOT/P44/ETH/SSH/WIFI**: NOT TESTED until separately
   authorized controlled trial, backups, recovery and hardware acceptance.

Do not merge parent PR #14, this Draft PR, or change the signing workflow
just to claim an unproven device result. New fail logs and exact rerun SHA
should be appended here after CI completes.

## Iteration evidence (2026-11-16 JST)

- [CI #43880739533](https://github.com/Karin-Laboratory/Debian13-Terminal6/actions/runs/43880739533):
  static 5 tests PASS; actual Linux `olddefconfig` stopped correctly at
  `PUBLIC_NETWORK_BUILTIN_REQUIRED: NET_DSA`. Linux 6.18.63
  `net/dsa/Kconfig` requires the higher-level `NETDEVICES=y`;
  enabled it and `ETHERNET=y`.
- [CI #43880987240](https://github.com/Karin-Laboratory/Debian13-Terminal6/actions/runs/43880987240):
  `NET_DSA`, `NET_MEDIATEK_SOC`, PCS and SGMII all resolved to `y`.
  Strict verifier reported missing `ARM64_VA_BITS_39` and `IPC_NS`.
  Added explicit `PAGE_SIZE_4KB` and `SYSVIPC`, confirmed from upstream
  ARM64 and `init/Kconfig` prerequisites.
- [CI #43881303197](https://github.com/Karin-Laboratory/Debian13-Terminal6/actions/runs/43881303197):
  IPC issue cleared; 39-bit VA still did not resolve. This is a Kconfig
  choice whose default is 52-bit; implemented explicit disable of other
  choice alternatives and fail-only selected-values diagnostics.
- [CI #43881774828](https://github.com/Karin-Laboratory/Debian13-Terminal6/actions/runs/43881774828):
  latest native public lean Image/P25 trial at commit
  `0682749d7127860078a9224dd472549271186df0`.
  **Outcome must be checked and recorded, not assumed.**
- [Private unsigned retention PR #162](https://github.com/Karin-Laboratory/SBAT6A-Offline-Archive/pull/162):
  exact public commit pinned, owner-private artifact only if Image,
  P25 independent verification and SHA receipts all pass.
  Its first run used an earlier config and failed safely. The newer
  pin's run must be verified independently.

The owner explicitly confirmed the 48.6MiB baseline **cannot boot**.
[Private PR #161](https://github.com/Karin-Laboratory/SBAT6A-Offline-Archive/pull/161)
was marked **DO NOT SIGN** for its old `4a456cfa...` candidate.
This lean development does not inherit that signing authorization.

## Verified public-build PASS (2026-11-16, 14:06 UTC)

Native ARM64 [CI #43881774828](https://github.com/Karin-Laboratory/Debian13-Terminal6/actions/runs/43881774828),
source commit `0682749d7127860078a9224dd472549271186df0`,
ended **success**. The 5 static regressions passed, then Linux 6.18.63
`olddefconfig` resolved C-unit builtins/modules and 39-bit VA to PASS.
The actual source-rebuilt kernel and modules compiled; the real 32 MiB
unsigned P25 passed the independent verifier.

| Evidence | Value |
|---|---|
| Uncompressed ARM64 Image | 9,211,912 bytes (8.79 MiB) |
| Uncompressed Image SHA256 | `17c34fcb0fbf4bee965d68458e8a2f3cc4c378c9d5b9d38f68c2467822a6c384` |
| Image.gz | 4,168,341 bytes |
| Same-build module tar | 583,680 bytes |
| Kernel config SHA256 | `210f43d38d09ae32a2b8cf89bda7085b13ae76624d3517746c26103de8de29e4` |
| Unsigned P25 | 33,554,432 bytes |
| Unsigned P25 SHA256 | `60c57d88e8d16aafb6f4b6ca5ec8b62384668eb99971344a9299866b3b82ea5c` |
| Independent P25 full readback | PASS |
| Signature, hardware LK boot, P44 LAN/SSH, Wi-Fi PHY | NOT TESTED |

The finished source branch also includes the one-command
`scripts/reproduce-terminal6-lean-p25.sh /absolute/NEW-output-dir`
for local replay. The actual native CI used the same underlying
`build-linux-6.18.sh` and P25 producer/verifier steps, not that
wrapper entrypoint.

**Important:** This public GitHub Actions run did not upload its
unsigned P25 artifact. The private archive PR #162 is running its own
source-pinned manufacture to retain the binary and final signing
candidate. Do not assume its SHA equals the public run because its
environment-generated initramfs and toolchain/package revisions may
differ. Owner approval must be specific to its actual private
full-readback SHA after the private check completes.
