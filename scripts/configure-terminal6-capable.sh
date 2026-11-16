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
# Distinguish this module ABI from prior private 6.18.63-debian-t6-proto2.
# Never rename modules to trick vermagic/versioned symbol checks.
scripts/config --set-str LOCALVERSION "-t6-public-capable"
scripts/config --disable LOCALVERSION_AUTO
echo "TERMINAL6_CAPABLE_KCONFIG_REQUESTED_NOT_YET_RESOLVED"
