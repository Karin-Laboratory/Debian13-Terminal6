#!/usr/bin/env bash
# SPDX-License-Identifier: MIT
# Complete explicit PCIe + USB source-only experimental DTB variant.
# Never changes existing public baseline DTB, owner eMMC or boot partitions.
set -euo pipefail
[[ $# -eq 1 && "$1" = /* ]] || { echo "usage: stage-pcie-usb-experimental-dtb.sh /absolute/PRE_STAGED_DTB_DIR" >&2; exit 2; }
stage="$1"
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
test -s "$stage/board/terminal6-debian-ethernet-experimental.dts"
test -s "$stage/board/terminal6-debian-ethernet-experimental.dtb"
for tool in python3 cpp dtc fdtget sha256sum; do command -v "$tool" >/dev/null || exit 2; done
out="$stage/board/terminal6-debian-pcie-usb-experimental"
python3 "$root/scripts/prepare-pcie-usb-experimental-dts.py" \
  "$stage/board/terminal6-debian-ethernet-experimental.dts" "$out.dts"
cpp -nostdinc -undef -D__DTS__ -x assembler-with-cpp \
  -I "$stage/include" -I "$stage/board" \
  "$out.dts" "$out-preprocessed.dts"
dtc -I dts -O dtb -o "$out.dtb" "$out-preprocessed.dts"
test -s "$out.dtb"
# Verify compiled FDT, not merely text in overlay source.
check_status() {
  local node="$1"
  test "$(fdtget -t s "$out.dtb" "$node" status)" = okay || {
    echo "EXPERIMENTAL_ENABLED_NODE_MISSING: $node" >&2
    exit 1
  }
}
for node in \
  /pcie@11280000 /pcie@11288000 /pcie@11290000 \
  /phy@11310000 /phy@11e00000 /phy@11e20000 \
  /usb@11201000 /usb@11201000/usb@11200000 \
  /usb-phy@11ec0000; do
  check_status "$node"
done
test "$(fdtget -t s "$out.dtb" /usb@11201000 dr_mode)" = host
for node in /phy@11310000 /phy@11e00000 /phy@11e20000; do
  fdtget -t s "$out.dtb" "$node" compatible | grep -Fq 'mediatek,mt6980-pcie-phy'
done
# Protect the eMMC 100MHz/no-CQE boot mitigation and management Ethernet.
test "$(fdtget -t x "$out.dtb" /mmc@11230000 max-frequency)" = 5f5e100
check_status /mmc@11230000
check_status /netsys@15100000/ethernet@15100000
echo 'CUNIT_PCIE_USB_COMPILED_DTB_NODES_ENABLED_SOURCE_ONLY_PASS'
echo 'NOT_A_SAFE_TO_FLASH_ASSERTION: PCIE_CLOCK_RESET_POWER_USB_VBUS_PHYSICAL_NOT_TESTED'
sha256sum "$out.dtb"
