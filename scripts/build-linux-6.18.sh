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
if [[ "${KERNEL_PROFILE:-generic}" = "minimal" ]]; then
  make ARCH=arm64 tinyconfig
  scripts/config --enable ARM64 --enable MMU --enable SMP \
    --enable BLOCK --enable MULTIUSER --enable TTY --enable SHMEM \
    --enable OF --enable ARCH_MEDIATEK \
    --enable COMMON_CLK --enable COMMON_CLK_MEDIATEK \
    --enable MFD_SYSCON --enable PINCTRL --enable PINCTRL_MTK \
    --enable REGULATOR --enable GPIOLIB \
    --enable SERIAL_8250_MT6577 --enable MMC_MTK \
    --enable MODULES --enable MODULE_UNLOAD
else
  make ARCH=arm64 defconfig
fi
scripts/config --enable DEVTMPFS --enable DEVTMPFS_MOUNT --enable BLK_DEV_INITRD \
  --enable EXT4_FS --enable MMC --enable MMC_BLOCK \
  --enable SERIAL_8250 --enable SERIAL_8250_CONSOLE \
  --enable CGROUPS --enable NAMESPACES --enable TMPFS \
  --enable UNIX --enable INET --enable NET \
  --enable USB_SUPPORT --enable USB --enable USB_SERIAL \
  --module USB_SERIAL_CH341 --enable OVERLAY_FS \
  --enable NFS_FS --enable NFS_V4
if [[ -n "${INITRAMFS_ARCHIVE:-}" ]]; then
  test -s "$INITRAMFS_ARCHIVE"
  scripts/config --set-str INITRAMFS_SOURCE "$INITRAMFS_ARCHIVE"
fi
make ARCH=arm64 olddefconfig
python3 "$ROOT/scripts/verify-kconfig.py" .config
export KBUILD_BUILD_USER=terminal6 KBUILD_BUILD_HOST=source-build
export KBUILD_BUILD_TIMESTAMP='Thu Jan  1 00:00:00 UTC 1970'
export SOURCE_DATE_EPOCH=0
make ARCH=arm64 -j"${JOBS:-4}" Image modules
test -s arch/arm64/boot/Image
mkdir -p "$WORKDIR/output"
cp arch/arm64/boot/Image "$WORKDIR/output/Image"
gzip -n -9 -c "$WORKDIR/output/Image" > "$WORKDIR/output/Image.gz"
if [[ -n "${DTB_PATH:-}" ]]; then
  test -s "$DTB_PATH"
  cp "$DTB_PATH" "$WORKDIR/output/terminal6-debian-experimental.dtb"
fi
cp .config "$WORKDIR/output/kernel.config"
sha256sum "$WORKDIR/output/Image" "$WORKDIR/output/Image.gz" "$WORKDIR/output/kernel.config" > "$WORKDIR/output/SHA256SUMS"
if [[ -n "${DTB_PATH:-}" ]]; then
  (cd "$WORKDIR/output" && sha256sum terminal6-debian-experimental.dtb) >> "$WORKDIR/output/SHA256SUMS"
fi
printf '%s\n' LINUX_IMAGE_BUILT_ONLY NOT_A_TERMINAL6_BOOT_IMAGE BOARD_DTB_UNVERIFIED P25_PACKAGING_UNVERIFIED > "$WORKDIR/output/STATUS.txt"
echo "ARM64_IMAGE_BUILT_WITH_OPTIONAL_P44_INITRAMFS; LK/DTB hardware compatibility not established"
