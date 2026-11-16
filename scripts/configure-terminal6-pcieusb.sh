#!/usr/bin/env bash
# SPDX-License-Identifier: MIT
# Inherit proven 35MiB-capable P44/KVM/LAN/MT7990 contract, then opt in
# to PCIe/USB DTB-specific host/PHY closure and independent module ABI.
set -euo pipefail
test -x scripts/config
test "$(make -s kernelversion)" = "6.18.63"
bash "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/configure-terminal6-capable.sh"
# MT6990's public DTSI uses "mediatek,xsphy" for USB2/USB3 and
# "mediatek,mtu3" at the host wrapper. These were absent in previous P25.
scripts/config --module PHY_MTK_XSPHY --module USB_MTU3   --enable USB_MTU3_HOST
# Never mix old -capable modules with this source-ported PCIe/USB kernel.
scripts/config --set-str LOCALVERSION "-t6-public-pcieusb"
scripts/config --disable LOCALVERSION_AUTO
echo TERMINAL6_PCIE_USB_HOST_KERNEL_KCONFIG_REQUESTED_NOT_RESOLVED
