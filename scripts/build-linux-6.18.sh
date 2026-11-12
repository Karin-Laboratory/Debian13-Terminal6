#!/usr/bin/env bash
# SPDX-License-Identifier: MIT
# Build generic ARM64 Linux 6.18.63. NOT a complete Terminal 6 P25.
set -euo pipefail
VERSION=6.18.63
: "${WORKDIR:?WORKDIR must point to a new absolute directory}"
case "$WORKDIR" in /*) ;; *) echo 'WORKDIR must be absolute' >&2; exit 2;; esac
test ! -e "$WORKDIR" || { echo 'Refusing existing WORKDIR' >&2; exit 2; }
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
for tool in git make python3 sha256sum; do command -v "$tool" >/dev/null; done
git clone --depth 1 --branch "v$VERSION" https://git.kernel.org/pub/scm/linux/kernel/git/stable/linux.git "$WORKDIR"
cd "$WORKDIR"
test "$(make -s kernelversion)" = "$VERSION"
make ARCH=arm64 defconfig
scripts/config --enable DEVTMPFS --enable DEVTMPFS_MOUNT --enable BLK_DEV_INITRD \
  --enable EXT4_FS --enable MMC --enable MMC_BLOCK \
  --enable SERIAL_8250 --enable SERIAL_8250_CONSOLE \
  --enable CGROUPS --enable NAMESPACES --enable TMPFS \
  --enable UNIX --enable INET --enable NET \
  --enable USB_SUPPORT --enable USB --enable USB_SERIAL \
  --module USB_SERIAL_CH341 --enable OVERLAY_FS \
  --enable NFS_FS --enable NFS_V4
make ARCH=arm64 olddefconfig
python3 "$ROOT/scripts/verify-kconfig.py" .config
export KBUILD_BUILD_USER=terminal6 KBUILD_BUILD_HOST=source-build
export KBUILD_BUILD_TIMESTAMP='Thu Jan  1 00:00:00 UTC 1970'
export SOURCE_DATE_EPOCH=0
make ARCH=arm64 -j"${JOBS:-4}" Image modules
test -s arch/arm64/boot/Image
mkdir -p "$WORKDIR/output"
cp arch/arm64/boot/Image "$WORKDIR/output/Image"
cp .config "$WORKDIR/output/kernel.config"
sha256sum "$WORKDIR/output/Image" "$WORKDIR/output/kernel.config" > "$WORKDIR/output/SHA256SUMS"
printf '%s\n' LINUX_IMAGE_BUILT_ONLY NOT_A_TERMINAL6_BOOT_IMAGE BOARD_DTB_UNVERIFIED P25_PACKAGING_UNVERIFIED > "$WORKDIR/output/STATUS.txt"
echo "GENERIC_ARM64_IMAGE_BUILT; board DTB and P25 packer are unresolved"
