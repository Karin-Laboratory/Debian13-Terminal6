#!/usr/bin/env bash
# SPDX-License-Identifier: MIT
set -euo pipefail
# Run on ARM64 host with busybox-static and cpio installed.
[[ $# -ge 2 && $# -le 4 ]] || { echo 'usage: make-initramfs.sh /absolute/busybox /absolute/output.cpio.gz' >&2; exit 2; }
busybox="$1"; output="$2"
[[ "$busybox" = /* && "$output" = /* && -f "$busybox" && ! -e "$output" ]] || exit 2
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
tmp="$(mktemp -d)"
trap 'rm -rf -- "$tmp"' EXIT
mkdir -p "$tmp"/{bin,dev,proc,sys,newroot}
cp "$busybox" "$tmp/bin/busybox"
for app in sh mount mountpoint umount sleep switch_root mkdir cp ln ip cat grep basename awk chmod sync kill mv unzip tar sha256sum wc uname chroot; do ln -s busybox "$tmp/bin/$app"; done
if [[ $# -ge 3 ]]; then
  test -d "$3" && test ! -L "$3"
  cp -a "$3" "$tmp/terminal6"
fi
if [[ $# -eq 4 ]]; then
  test -d "$4" && test ! -L "$4"
  cp -a "$4/." "$tmp/"
  mkdir -p "$tmp/terminal6-rescue-root"
  cp -a "$4/." "$tmp/terminal6-rescue-root/"
  test -s "$tmp/terminal6-rescue-root/terminal6-rescue.service"
  test -x "$tmp/sbin/terminal6-rescue"
  test -x "$tmp/sbin/dropbear"
  test -x "$tmp/sbin/dropbearkey"
  test -x "$tmp/sbin/terminal6-firstboot"
  test -x "$tmp/sbin/terminal6-install-p44"
  test -x "$tmp/sbin/gnu-tar"
fi
cp "$root/initramfs/init" "$tmp/init"
chmod 755 "$tmp/init" "$tmp/bin/busybox"
# Owner IDs are always stable; no device nodes are required with devtmpfs.
# For public lean P25 reproducibility, the cpio inode/device numbers and the
# timestamps of *all* files, directories and symlinks must also be stable.
# Keep this opt-in so unrelated historic P25 recipes do not silently change.
if [[ "${TERMINAL6_REPRODUCIBLE_INITRAMFS:-0}" = 1 ]]; then
  epoch="${SOURCE_DATE_EPOCH:-0}"
  [[ "$epoch" =~ ^[0-9]+$ ]] || { echo 'Invalid SOURCE_DATE_EPOCH' >&2; exit 2; }
  find "$tmp" -print0 | xargs -0 -r touch -h -d "@$epoch"
  (cd "$tmp" && find . -print0 | LC_ALL=C sort -z | \
    cpio --null -o -H newc --quiet --owner=0:0 --reproducible | gzip -n -9) > "$output"
else
  (cd "$tmp" && find . -print0 | LC_ALL=C sort -z | \
    cpio --null -o -H newc --quiet --owner=0:0 | gzip -n -9) > "$output"
fi
gzip -t "$output"
echo "P44_INITRAMFS_CPIO_BUILT $(sha256sum "$output")"
