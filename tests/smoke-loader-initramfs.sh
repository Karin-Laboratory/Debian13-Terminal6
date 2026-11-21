#!/usr/bin/env bash
# SPDX-License-Identifier: MIT
# Executes actual packaged ARM64 helpers in an isolated, unmounted chroot.
# Never operates on a real block device, partition, or boot-control record.
set -euo pipefail
[[ $# -eq 1 && "$1" = /* && -s "$1" ]] || {
  echo 'usage: smoke-loader-initramfs.sh /absolute/initramfs.cpio.gz' >&2; exit 2;
}
[[ "$(uname -m)" == aarch64 ]] || { echo 'NATIVE_ARM64_REQUIRED'; exit 42; }
for tool in sudo chroot gzip cpio mkfs.ext4 mksquashfs python3; do
  command -v "$tool" >/dev/null || { echo "MISSING_TEST_HELPER:$tool"; exit 42; }
done
tmp="$(mktemp -d)"
trap 'rm -rf -- "$tmp"' EXIT
mkdir -p "$tmp"/{fixtures,config,userdata,proc}
(cd "$tmp" && gzip -dc "$1" | cpio --quiet -idm)
test -x "$tmp/sbin/blkid" && test ! -L "$tmp/sbin/blkid"
test -x "$tmp/sbin/mountpoint" && test ! -L "$tmp/sbin/mountpoint"
for app in sh mount umount ip cat grep sed mkdir ln chmod sync passwd; do
  sudo chroot "$tmp" /bin/busybox --list | grep -x "$app" >/dev/null || { echo "BUSYBOX_APPLET_FAIL:$app"; exit 42; }
done
sudo chroot "$tmp" /sbin/blkid --help >/dev/null 2>&1 || {
  echo 'ARM64_REAL_BLKID_RUNTIME_FAIL'; exit 42;
}
sudo chroot "$tmp" /sbin/mountpoint --help >/dev/null 2>&1 || {
  echo 'ARM64_REAL_MOUNTPOINT_RUNTIME_FAIL'; exit 42;
}
# No kernel mount permissions are needed: test filesystem signatures in files.
truncate -s 16M "$tmp/fixtures/p26.ext4"
mkfs.ext4 -F -q "$tmp/fixtures/p26.ext4"
mkdir -p "$tmp/squash-source"
printf 'stock\n' > "$tmp/squash-source/test.txt"
mksquashfs "$tmp/squash-source" "$tmp/fixtures/p26.squashfs" -processors 1 -quiet -noappend >/dev/null
printf 'not a filesystem' > "$tmp/fixtures/p26.corrupt"
probe() { sudo chroot "$tmp" /sbin/blkid -s TYPE -o value "$1" 2>/dev/null || :; }
[[ "$(probe /fixtures/p26.ext4)" == ext4 ]] || {
  echo 'P26_EXT4_PROBE_FAIL'; exit 42;
}
[[ "$(probe /fixtures/p26.squashfs)" == squashfs ]] || {
  echo 'P26_SQUASHFS_PROBE_FAIL'; exit 42;
}
[[ "$(probe /fixtures/p26.corrupt)" != ext4 ]] || {
  echo 'P26_CORRUPTION_FALSE_EXT4'; exit 42;
}
[[ -z "$(probe /fixtures/nonexistent)" ]] || {
  echo 'P26_MISSING_FALSE_FS'; exit 42;
}
# An unmounted directory must not be mistaken for an active P43/P26 mount.
if sudo chroot "$tmp" /sbin/mountpoint -q /userdata; then
  echo 'UNMOUNTED_P43_FALSE_POSITIVE'; exit 42;
fi
if sudo chroot "$tmp" /sbin/mountpoint -q /config; then
  echo 'UNMOUNTED_P26_FALSE_POSITIVE'; exit 42;
fi
# Source must never try to format a real P26/P43 or silently mutate B.
! grep -Eq '(^|[[:space:]])(mkfs|parted|sfdisk|sgdisk|dd)[[:space:]]' "$tmp/init"
echo 'LOADER_REAL_ARM64_HELPER_RUNTIME_PASS'
echo 'LOADER_OFFLINE_P26_ABSENT_SQUASHFS_EXT4_CORRUPT_NEGATIVE_GATES_PASS'
echo 'LOADER_INITRAMFS_NO_DEVICE_WRITES'
