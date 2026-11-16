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
# Official stable v6.18.63 commit, independently confirmed via public tag.
EXPECTED_LINUX_SHA=1cdda838e8475edf89b73ff0cc952005dd0b1fa7
if ! git clone -q --depth 1 --branch "v$VERSION" \
  https://github.com/gregkh/linux.git "$WORKDIR"; then
  rm -rf -- "$WORKDIR"
  git clone -q --depth 1 --branch "v$VERSION" \
    https://git.kernel.org/pub/scm/linux/kernel/git/stable/linux.git "$WORKDIR"
fi
test "$(git -C "$WORKDIR" rev-parse HEAD)" = "$EXPECTED_LINUX_SHA"
cd "$WORKDIR"
test "$(make -s kernelversion)" = "$VERSION"
if [[ -n "${PUBLIC_MT6990_STAGE:-}" ]]; then
  python3 "$ROOT/scripts/apply-public-mt6990-kernel.py" \
    --source-stage "$PUBLIC_MT6990_STAGE" \
    --kernel-tree "$WORKDIR" --scope "${PUBLIC_MT6990_SCOPE:-core}" \
    --receipt "$WORKDIR/public-mt6990-kernel-inputs.json"
  python3 "$ROOT/scripts/port-public-mt6990-clock.py" \
    "$WORKDIR/drivers/clk/mediatek/clk-mt6990.c"
fi
if [[ "${KERNEL_PROFILE:-generic}" = "terminal6-capable" || "${KERNEL_PROFILE:-generic}" = "terminal6-pcieusb" ]]; then
  # Source-only hardware-calibration fix from public Debian PR #9, derived
  # from openwrt/mt76. No firmware, per-device EEPROM/OTP bytes or RF I/O.
  # CI independently checked applicability to pristine stable Linux 6.18.63.
  public_otp_patch="$ROOT/patches/mt7990-public-otp-calfree-timeout.patch"
  test -s "$public_otp_patch"
  git apply --check "$public_otp_patch"
  git apply "$public_otp_patch"
  grep -Fq 'mt7996_mcu_get_cal_free_data' drivers/net/wireless/mediatek/mt76/mt7996/mcu.c
  grep -Fq 'mdev->mcu.timeout = 30 * HZ' drivers/net/wireless/mediatek/mt76/mt7996/mcu.c
  echo 'PUBLIC_MT7990_CALFREE_OTP_TIMEOUT_SOURCE_PATCH_PASS'
fi
if [[ "${KERNEL_PROFILE:-generic}" = "terminal6-pcieusb" ]]; then
  # Public donor: 13179415360/openwrt-mt6990-lg6851f,
  # source commit a40df9a5afb46716dea799acea69f17480df4d82.
  test -s "$ROOT/patches/mt6990-public-pcie-gen3.patch"
  git apply --check "$ROOT/patches/mt6990-public-pcie-gen3.patch"
  git apply "$ROOT/patches/mt6990-public-pcie-gen3.patch"
  python3 "$ROOT/scripts/port-mt6990-pcie-phy.py" \
    "$ROOT/patches/mt6990-public-pcie-phy.patch" \
    "$WORKDIR/drivers/phy/mediatek/phy-mtk-pcie.c"
  grep -Fq 'mediatek,mt6990-pcie' drivers/pci/controller/pcie-mediatek-gen3.c
  grep -Fq 'mediatek,mt6980-pcie-phy' drivers/phy/mediatek/phy-mtk-pcie.c
  echo 'PUBLIC_MT6990_PCIE_HOST_AND_PHY_PATCHES_APPLIED'
fi
if [[ "${KERNEL_PROFILE:-generic}" = "terminal6-lean" || "${KERNEL_PROFILE:-generic}" = "terminal6-capable" || "${KERNEL_PROFILE:-generic}" = "terminal6-pcieusb" ]]; then
  test -n "${PUBLIC_MT6990_STAGE:-}" && test "${PUBLIC_MT6990_SCOPE:-}" = network || { echo "terminal6 source profile requires public network MT6990 source stage" >&2; exit 2; }
  make ARCH=arm64 tinyconfig
  if [[ "${KERNEL_PROFILE}" = "terminal6-pcieusb" ]]; then
    bash "$ROOT/scripts/configure-terminal6-pcieusb.sh"
  elif [[ "${KERNEL_PROFILE}" = "terminal6-capable" ]]; then
    bash "$ROOT/scripts/configure-terminal6-capable.sh"
  else
    bash "$ROOT/scripts/configure-terminal6-lean.sh"
  fi
elif [[ "${KERNEL_PROFILE:-generic}" = "minimal" ]]; then
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
if [[ -n "${PUBLIC_MT6990_STAGE:-}" ]]; then
  scripts/config --enable COMMON_CLK_MT6990 --enable ARCH_MEDIATEK
fi
if [[ -n "${PUBLIC_MT6990_STAGE:-}" && "${PUBLIC_MT6990_SCOPE:-core}" = network ]]; then
  # NET_DSA=m or HSR=m caps NET_MEDIATEK_SOC at module tristate.
  # P25 must have built-in Ethernet/PCS before Debian P44 userspace starts.
  scripts/config --disable HSR --enable IPV6
  scripts/config --enable COMMON_CLK_MT6990_PERI --enable BRIDGE \
    --enable NET_DSA --enable NET_VENDOR_MEDIATEK \
    --enable NET_MEDIATEK_SOC --enable PCS_MTK_LYNXI \
    --enable NET_DSA_MT7530 --enable NET_DSA_MT7530_MDIO \
    --enable PHY_MTK_MT6990_SGMII --enable PHYLINK
fi
scripts/config --enable PRINTK --enable PRINTK_TIME --enable BINFMT_ELF \
  --enable BINFMT_SCRIPT --enable ARM_GIC --enable ARM_GIC_V3 \
  --enable ARM_ARCH_TIMER --enable SERIAL_EARLYCON --enable SERIAL_8250_MT6577 \
  --enable RD_GZIP --enable EFI_PARTITION --enable MMC_MTK \
  --enable PROC_FS --enable SYSFS --enable FUTEX --enable EPOLL \
  --enable SIGNALFD --enable TIMERFD --enable INOTIFY_USER \
  --enable IKCONFIG --enable IKCONFIG_PROC
scripts/config --enable DEVTMPFS --enable DEVTMPFS_MOUNT --enable BLK_DEV_INITRD \
  --enable EXT4_FS --enable MMC --enable MMC_BLOCK \
  --enable SERIAL_8250 --enable SERIAL_8250_CONSOLE \
  --enable CGROUPS --enable NAMESPACES --enable TMPFS \
  --enable UNIX --enable INET --enable NET \
  --enable IKCONFIG --enable IKCONFIG_PROC
if [[ "${KERNEL_PROFILE:-generic}" != terminal6-lean && "${KERNEL_PROFILE:-generic}" != terminal6-capable && "${KERNEL_PROFILE:-generic}" != terminal6-pcieusb ]]; then
  scripts/config --enable USB_SUPPORT --enable USB --enable USB_SERIAL \
    --module USB_SERIAL_CH341 --enable OVERLAY_FS \
    --enable NFS_FS --enable NFS_V4
fi
if [[ -n "${INITRAMFS_ARCHIVE:-}" ]]; then
  test -s "$INITRAMFS_ARCHIVE"
  scripts/config --set-str INITRAMFS_SOURCE "$INITRAMFS_ARCHIVE"
fi
make ARCH=arm64 olddefconfig
if [[ -n "${PUBLIC_MT6990_STAGE:-}" && "${PUBLIC_MT6990_SCOPE:-core}" = network ]]; then
  grep -E '^CONFIG_(NET_DSA|BRIDGE|HSR|NET_MEDIATEK_SOC|PCS_MTK_LYNXI|PHY_MTK_MT6990_SGMII|COMMON_CLK_MT6990_PERI)=' .config || :
  for key in NET_DSA NET_MEDIATEK_SOC PCS_MTK_LYNXI PHY_MTK_MT6990_SGMII; do
    grep -qx "CONFIG_${key}=y" .config || { echo "PUBLIC_NETWORK_BUILTIN_REQUIRED: ${key}" >&2; exit 1; }
  done
fi
if [[ "${KERNEL_PROFILE:-generic}" = "terminal6-pcieusb" ]]; then
  python3 "$ROOT/scripts/verify-terminal6-pcieusb-config.py" .config
elif [[ "${KERNEL_PROFILE:-generic}" = "terminal6-capable" ]]; then
  python3 "$ROOT/scripts/verify-terminal6-capable-config.py" .config
elif [[ "${KERNEL_PROFILE:-generic}" = "terminal6-lean" ]]; then
  python3 "$ROOT/scripts/verify-kconfig.py" --terminal6 --lean .config
else
  python3 "$ROOT/scripts/verify-kconfig.py" .config
fi
if [[ "${KERNEL_PROFILE:-generic}" = "minimal" ]]; then
  for option in ARCH_MEDIATEK MMC_MTK SERIAL_8250_MT6577; do
    grep -qx "CONFIG_${option}=y" .config || {
      echo "Terminal 6 built-in driver missing: CONFIG_${option}=y" >&2
      exit 1
    }
  done
  echo MEDIATEK_MMC_UART_BUILTIN_KCONFIG_PASS
fi
export KBUILD_BUILD_USER=terminal6 KBUILD_BUILD_HOST=source-build
export KBUILD_BUILD_TIMESTAMP='Thu Jan  1 00:00:00 UTC 1970'
export SOURCE_DATE_EPOCH=0
if [[ "${KERNEL_PROFILE:-generic}" = terminal6-capable || "${KERNEL_PROFILE:-generic}" = terminal6-pcieusb ]]; then
  # Linux 6.18 scripts/setlocalversion appends '+' for a dirty source when
  # LOCALVERSION is unset, even if CONFIG_LOCALVERSION_AUTO is disabled.
  # Setting it to an explicit EMPTY string preserves only our distinct
  # CONFIG_LOCALVERSION=-t6-public-capable without disguising private ABI.
  export LOCALVERSION=""
fi
make ARCH=arm64 -j"${JOBS:-4}" Image modules
if [[ "${KERNEL_PROFILE:-generic}" = terminal6-capable || "${KERNEL_PROFILE:-generic}" = terminal6-pcieusb ]]; then
  release="$(make -s ARCH=arm64 kernelrelease)"
  expected_release='6.18.63-t6-public-capable'
  [[ "${KERNEL_PROFILE:-generic}" = terminal6-pcieusb ]] && expected_release='6.18.63-t6-public-pcieusb'
  test "$release" = "$expected_release" || {
    echo "TERMINAL6_CAPABLE_MODULE_RELEASE_MISMATCH: $release" >&2
    exit 42
  }
  echo "TERMINAL6_CAPABLE_EXACT_KERNELRELEASE_PASS $release"
fi
module_name="terminal6-lean-modules.tar"
if [[ "${KERNEL_PROFILE:-generic}" = terminal6-capable || "${KERNEL_PROFILE:-generic}" = terminal6-pcieusb ]]; then
  module_name="terminal6-capable-modules.tar"
  if [[ "${KERNEL_PROFILE:-generic}" = terminal6-pcieusb ]]; then
    module_name="terminal6-pcieusb-modules.tar"
  fi
fi
if [[ "${KERNEL_PROFILE:-generic}" = terminal6-lean || "${KERNEL_PROFILE:-generic}" = terminal6-capable || "${KERNEL_PROFILE:-generic}" = terminal6-pcieusb ]]; then
  make ARCH=arm64 INSTALL_MOD_PATH="$WORKDIR/output/module-tree" modules_install
  test -d "$WORKDIR/output/module-tree/lib/modules"
  (cd "$WORKDIR/output/module-tree" && tar -cf "$WORKDIR/output/$module_name" lib/modules)
fi
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
if [[ "${KERNEL_PROFILE:-generic}" = terminal6-lean || "${KERNEL_PROFILE:-generic}" = terminal6-capable || "${KERNEL_PROFILE:-generic}" = terminal6-pcieusb ]]; then
  # The Air Terminal 6 boot_a P25 is exactly 32 MiB as a *partition*;
  # 35 MiB is the separate cap on the decompressed Image.
  image_bytes="$(stat -c %s "$WORKDIR/output/Image")"
  image_max=33554432
  if [[ "${KERNEL_PROFILE:-generic}" = terminal6-capable || "${KERNEL_PROFILE:-generic}" = terminal6-pcieusb ]]; then image_max=36700160; fi
  test "$image_bytes" -le "$image_max" || {
    echo "TERMINAL6_IMAGE_OVER_PROFILE_LIMIT: actual=$image_bytes allowed=$image_max" >&2; exit 42;
  }
  size vmlinux > "$WORKDIR/output/vmlinux-size.txt"
  test -s "$WORKDIR/output/vmlinux-size.txt"
  test -s "$WORKDIR/output/$module_name"
  sha256sum "$WORKDIR/output/$module_name" >> "$WORKDIR/output/SHA256SUMS"
  printf 'TERMINAL6_%s_UNCOMPRESSED_IMAGE_SIZE_PASS bytes=%s max=%s\n' "${KERNEL_PROFILE#terminal6-}" "$image_bytes" "$image_max"
fi
if [[ -n "${DTB_PATH:-}" ]]; then
  (cd "$WORKDIR/output" && sha256sum terminal6-debian-experimental.dtb) >> "$WORKDIR/output/SHA256SUMS"
fi
printf '%s\n' LINUX_IMAGE_BUILT_ONLY NOT_A_TERMINAL6_BOOT_IMAGE BOARD_DTB_UNVERIFIED P25_PACKAGING_UNVERIFIED > "$WORKDIR/output/STATUS.txt"
if [[ -n "${PUBLIC_MT6990_STAGE:-}" ]]; then
  cp "$WORKDIR/public-mt6990-kernel-inputs.json" "$WORKDIR/output/public-mt6990-kernel-inputs.json"
  echo "PUBLIC_MT6990_STABLE_KERNEL_SOURCE_REPLAY_AND_BUILD_APPLIED; LK/board not verified"
fi
echo "ARM64_IMAGE_BUILT_WITH_OPTIONAL_P44_INITRAMFS; LK/DTB hardware compatibility not established"
