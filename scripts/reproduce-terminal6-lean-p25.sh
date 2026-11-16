#!/usr/bin/env bash
# SPDX-License-Identifier: MIT
# Public OSS-only Terminal6 lean P25 manufacturing. Never signs or flashes.
set -euo pipefail
[[ $# -eq 1 ]] || { echo 'usage: reproduce-terminal6-lean-p25.sh /absolute/NEW-output-dir' >&2; exit 2; }
out="$1"
[[ "$out" = /* && "$out" != "/" && ! -e "$out" && ! -L "$out" ]] || {
  echo 'Expected a new absolute non-symlink output directory' >&2
  exit 2
}
[[ "$(uname -m)" = aarch64 ]] || { echo 'Native ARM64 host required' >&2; exit 2; }
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
for bin in git make python3 cpp dtc cpio gzip curl sha256sum tar size; do
  command -v "$bin" >/dev/null || { echo "Missing build tool: $bin" >&2; exit 2; }
done
test -f /bin/busybox || { echo 'Install busybox-static' >&2; exit 2; }
umask 077
mkdir -m 0700 "$out"
python3 -m unittest discover -s "$root/tests" -p 'test_terminal6_lean_config.py' -v
bash "$root/scripts/make-initramfs.sh" /bin/busybox "$out/initramfs.cpio.gz"
bash "$root/scripts/stage-experimental-dtb.sh" "$out/dtb"
python3 "$root/scripts/stage-public-mt6990-sources.py" --output "$out/stage"
KERNEL_PROFILE=terminal6-lean PUBLIC_MT6990_SCOPE=network \
PUBLIC_MT6990_STAGE="$out/stage" WORKDIR="$out/linux" \
INITRAMFS_ARCHIVE="$out/initramfs.cpio.gz" \
DTB_PATH="$out/dtb/board/terminal6-debian-ethernet-experimental.dtb" \
JOBS="${JOBS:-4}" bash "$root/scripts/build-linux-6.18.sh"
python3 "$root/scripts/assemble-template-free-p25.py" \
  --source-stage "$out/stage" \
  --profile "$root/configs/public-air6-boot-v2-profile.json" \
  --kernel-image "$out/linux/output/Image" \
  --initramfs-cpio-gz "$out/initramfs.cpio.gz" \
  --dtb "$out/dtb/board/terminal6-debian-ethernet-experimental.dtb" \
  --output "$out/p25"
python3 "$root/scripts/verify-public-unsigned-p25.py" \
  --p25 "$out/p25/p25-unsigned.img" \
  --kernel-image "$out/linux/output/Image" \
  --initramfs-cpio-gz "$out/initramfs.cpio.gz" \
  --dtb "$out/dtb/board/terminal6-debian-ethernet-experimental.dtb" \
  --profile "$root/configs/public-air6-boot-v2-profile.json" \
  --receipt "$out/p25/p25-receipt.json"
test "$(stat -c %s "$out/linux/output/Image")" -le 33554432
test "$(stat -c %s "$out/p25/p25-unsigned.img")" = 33554432
sha256sum "$out/linux/output/Image" "$out/p25/p25-unsigned.img"
printf '%s\n' 'TERMINAL6_LEAN_PUBLIC_SOURCE_UNSIGNED_P25_INDEPENDENT_READBACK_PASS' \
  'LK_PHYSICAL_BOOT_NOT_TESTED' 'NO_SIGNATURE' 'NO_DEVICE_CHANGE'
