#!/usr/bin/env bash
# SPDX-License-Identifier: MIT
# Public OSS C-unit capable profile. Runs after the verified lean profile.
# No signature, device deployment, proprietary firmware or calibration.
set -euo pipefail
test -x scripts/config
test "$(make -s kernelversion)" = 6.18.63
# Inherit all mandatory P44, MMC, UART, NETSYS, MT7531 and systemd features.
bash "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/configure-terminal6-lean.sh"
# KVM on arm64 is a bool built into Image, not a loadable module.
scripts/config --enable VIRTUALIZATION --enable KVM
# PCIe host support MUST precede any MT7990/MT7996 PHY registration.
# Generic public host/PHY drivers compile; C-unit's live PCIe DTS is
# experimental and the vendor-specific 7990 calibration fix is not included.
scripts/config --enable PCI --enable PCI_MSI --enable PCIE_MEDIATEK_GEN3 \
  --enable PHY_MTK_PCIE --enable PCIE_MEDIATEK
scripts/config --enable WIRELESS --enable WLAN --enable RFKILL
scripts/config --module CFG80211 --module MAC80211 --module MT7996E
# Keep USB host and common peripherals modular to preserve LK Image budget.
scripts/config --enable USB_SUPPORT --enable USB --enable USB_COMMON
scripts/config --module USB_XHCI_HCD --module USB_XHCI_MTK \
  --module PHY_MTK_TPHY --module USB_SERIAL \
  --module USB_SERIAL_CH341 --module SCSI --module BLK_DEV_SD \
  --module USB_STORAGE
# Restore boot-proven KVM-proto2 early ARM64 execution capabilities before
# olddefconfig. The C-unit LK has handed the kernel to 0xfd900000 (1MiB
# off a 2MiB alignment boundary); the previous public-capable kernel had
# RELOCATABLE=n while the boot-proven KVM-proto2 kernel has RELOCATABLE=y.
# This is a host-build hypothesis, NOT proof that the placement was causal.
# Keep earlycon in the existing cmdline and enable OF-probed serial as well.
scripts/config --enable RELOCATABLE --enable RANDOMIZE_BASE \
  --enable SERIAL_OF_PLATFORM --set-val NR_CPUS 4
# C-unit has GPT rootfs_data at P44. Match the boot-proven KVM eMMC
# allocation and fixed-voltage regulator support, not tinyconfig's defaults.
# This does NOT supply the missing MT69XX pinctrl OF driver: the private
# C-unit boot image must fix that dependency separately and verify the FDT.
scripts/config --set-val MMC_BLOCK_MINORS 64 --enable REGULATOR_FIXED_VOLTAGE
# Distinguish this module ABI from prior private 6.18.63-debian-t6-proto2.
# Never rename modules to trick vermagic/versioned symbol checks.
scripts/config --set-str LOCALVERSION "-t6-public-capable"
scripts/config --disable LOCALVERSION_AUTO
echo "TERMINAL6_CAPABLE_KCONFIG_REQUESTED_NOT_YET_RESOLVED"
