#!/usr/bin/env bash
# SPDX-License-Identifier: MIT
# Third-party offline-from-private-inputs replay: unsigned 32MiB P25 only.
# Uses NETWORK=network by default. No signing, flash, boot-slot changes or RF.
set -euo pipefail
[[ $# -eq 1 ]] || { echo "usage: $0 /absolute/NEW-output-directory" >&2; exit 2; }
out="$1"
[[ "$out" = /* && "$out" != / && ! -e "$out" && ! -L "$out" ]] || exit 2
[[ "$(uname -m)" = aarch64 ]] || { echo "native ARM64 Linux build host required" >&2; exit 2; }
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
for bin in git make python3 cpp dtc cpio gzip curl sha256sum; do
  command -v "$bin" >/dev/null || { echo "missing tool: $bin" >&2; exit 2; }
done
[[ -f /bin/busybox ]] || { echo "install busybox-static first" >&2; exit 2; }
# Every output path is fresh and under the user-selected root. The only
# downloaded inputs are SHA/commit-pinned public Linux/OSS source texts.
mkdir -m 0700 "$out"
bash "$root/scripts/stage-experimental-dtb.sh" "$out/dtb"
bash "$root/scripts/make-initramfs.sh" /bin/busybox "$out/p44-initramfs.cpio.gz"
python3 "$root/scripts/stage-public-mt6990-sources.py" \
  --output "$out/public-mt6990"
export PUBLIC_MT6990_STAGE="$out/public-mt6990"
export PUBLIC_MT6990_SCOPE=network
export WORKDIR="$out/linux-6.18.63"
export INITRAMFS_ARCHIVE="$out/p44-initramfs.cpio.gz"
export DTB_PATH="$out/dtb/board/terminal6-debian-ethernet-experimental.dtb"
export JOBS="${JOBS:-4}"
bash "$root/scripts/build-linux-6.18.sh"
python3 "$root/scripts/assemble-template-free-p25.py" \
  --source-stage "$out/public-mt6990" \
  --profile "$root/configs/public-air6-boot-v2-profile.json" \
  --kernel-image "$out/linux-6.18.63/output/Image" \
  --initramfs-cpio-gz "$out/p44-initramfs.cpio.gz" \
  --dtb "$out/dtb/board/terminal6-debian-ethernet-experimental.dtb" \
  --output "$out/unsigned-p25"
python3 "$root/scripts/verify-public-unsigned-p25.py" \
  --p25 "$out/unsigned-p25/p25-unsigned.img" \
  --kernel-image "$out/linux-6.18.63/output/Image" \
  --initramfs-cpio-gz "$out/p44-initramfs.cpio.gz" \
  --dtb "$out/dtb/board/terminal6-debian-ethernet-experimental.dtb" \
  --profile "$root/configs/public-air6-boot-v2-profile.json" \
  --receipt "$out/unsigned-p25/p25-receipt.json"
sha256sum "$out/unsigned-p25/p25-unsigned.img"
printf '%s\n' \
  'PUBLIC_OSS_32M_UNSIGNED_P25_INDEPENDENT_SOURCE_REPLAY_PASS' \
  'BOARD_DTB_LK_NOT_DEVICE_VALIDATED' \
  'P44_MANAGEMENT_ETHERNET_SSH_NOT_DEVICE_VALIDATED' \
  'NO_OWNER_SIGNATURE_OR_DEVICE_WRITE'
