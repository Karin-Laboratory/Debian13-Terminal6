#!/usr/bin/env bash
# SPDX-License-Identifier: MIT
# Build from the public lean profile, restoring the hardware capabilities that
# were excluded solely for size. Never claim physical C-unit compatibility.
set -euo pipefail
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
bash "$root/scripts/configure-terminal6-lean.sh"
test "$(make -s kernelversion)" = "6.18.63"
# KVM must be built into the ARM64 Image; independent physical EL2 acceptance
# was achieved only by a DIFFERENT owner-private C-unit kernel.
scripts/config --enable VIRTUALIZATION --enable KVM
# The MT7990/MT7991 radios are PCIe endpoints: keep the PCIe host side built
# in, mac80211/mt76 as same-kernel modules. Board-specific radio calibration
# and firmware are NOT present in public software and remain separate gates.
scripts/config --enable PCI --enable PCI_MSI --enable PCIEPORTBUS   --enable PCIE_MEDIATEK_GEN3 --enable FW_LOADER   --enable WIRELESS --enable WLAN --enable RFKILL   --enable NET --enable CRYPTO --enable CRYPTO_AEAD   --module CFG80211 --module MAC80211   --module MT76 --module MT76_CONNAC_LIB --module MT7996E
# USB controller and conventional USB serial support may remain modular,
# but kernel USB infrastructure must be present. USB host VBUS and physical
# device transfer are separate C-unit acceptance gates.
scripts/config --enable USB_SUPPORT --enable USB --enable USB_COMMON   --module USB_XHCI_HCD --module USB_XHCI_PLATFORM   --module USB_SERIAL --module USB_SERIAL_CH341
# Other useful generic storage/network functionality: not radio operations.
scripts/config --module NFS_FS --module NFS_V4 --module VFAT_FS   --module USB_STORAGE
# Constrain memory use and diagnostic footprint without dropping essential
# boot/P44/NETSYS/MT7531 or changing any owner-protected signer rules.
scripts/config --enable CC_OPTIMIZE_FOR_SIZE   --disable DEBUG_INFO --disable DEBUG_INFO_BTF
printf '%s\n' TERMINAL6_FULL35_KCONFIG_REQUESTED_NOT_YET_RESOLVED
