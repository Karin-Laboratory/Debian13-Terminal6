#!/usr/bin/env bash
# SPDX-License-Identifier: MIT
set -euo pipefail
# Run on ARM64 host with busybox-static and cpio installed.
[[ $# -eq 2 || $# -eq 3 ]] || { echo 'usage: make-initramfs.sh /absolute/busybox /absolute/output.cpio.gz' >&2; exit 2; }
busybox="$1"; output="$2"
[[ "$busybox" = /* && "$output" = /* && -f "$busybox" && ! -e "$output" ]] || exit 2
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
tmp="$(mktemp -d)"
trap 'rm -rf -- "$tmp"' EXIT
mkdir -p "$tmp"/{bin,dev,proc,sys,newroot}
cp "$busybox" "$tmp/bin/busybox"
for app in sh mount umount sleep switch_root mkdir cp ln; do ln -s busybox "$tmp/bin/$app"; done
if [[ $# -eq 3 ]]; then
  test -d "$3" && test ! -L "$3"
  cp -a "$3" "$tmp/terminal6"
fi
cp "$root/initramfs/init" "$tmp/init"
chmod 755 "$tmp/init" "$tmp/bin/busybox"
# preserve deterministic ownership; no device nodes are required with devtmpfs.
(cd "$tmp" && find . -print0 | LC_ALL=C sort -z | cpio --null -o -H newc --quiet --owner=0:0 | gzip -n -9) > "$output"
gzip -t "$output"
echo "P44_INITRAMFS_CPIO_BUILT $(sha256sum "$output")"
