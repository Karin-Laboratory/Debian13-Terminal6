#!/usr/bin/env bash
# Inspect a prospective independent Linux 802.11s peer without changing RF,
# device state, addresses, drivers, or network configuration.
set -euo pipefail
if [[ $# -ne 1 || ! $1 =~ ^phy[0-9]+$ ]]; then
    echo 'usage: bash scripts/mesh_peer_readonly_preflight.sh phyN' >&2
    exit 2
fi
phy=$1
for tool in iw ip wpa_supplicant; do
    command -v "$tool" >/dev/null || { echo "PEER_MISSING_TOOL=$tool"; exit 2; }
done
if [[ ! -d /sys/class/ieee80211/$phy ]]; then
    echo 'PEER_PHY_FOUND=FAIL'
    exit 1
fi
details=$(iw phy "$phy" info)
echo 'PEER_PHY_FOUND=PASS'
if grep -Eq '^[[:space:]]+\*[[:space:]]+mesh point([[:space:]]*)$' <<<"$details"; then
    echo 'PEER_MESH_POINT_ADVERTISED=PASS'
else
    echo 'PEER_MESH_POINT_ADVERTISED=FAIL'
    exit 1
fi
# The fact that 2437 MHz appears in a PHY dump is not authorization to TX.
if grep -Eq '2437 MHz' <<<"$details"; then
    echo 'PEER_2437_MHZ_VISIBLE=YES_CHECK_REGULATORY_FLAGS'
else
    echo 'PEER_2437_MHZ_VISIBLE=NO'
fi
if grep -q 'valid interface combinations:' <<<"$details"; then
    echo 'PEER_INTERFACE_COMBINATIONS_PRESENT=YES_REVIEW_MANUALLY'
else
    echo 'PEER_INTERFACE_COMBINATIONS_PRESENT=NO_REVIEW_MANUALLY'
fi
if [[ -e /lib/firmware/htc_9271.fw || -e /usr/lib/firmware/htc_9271.fw ]]; then
    echo 'PEER_ATH9K_HTC_FIRMWARE_FILE=FOUND_IF_AR9271'
else
    echo 'PEER_ATH9K_HTC_FIRMWARE_FILE=NOT_FOUND_IF_AR9271'
fi
echo 'PEER_WPA_SUPPLICANT_PRESENT=YES_CHECK_AMPE_SECURITY_PATCH'
echo 'PEER_REGDOMAIN_AND_NO_IR=REVIEW_WITH_iw_reg_get'
echo 'PEER_SAE_AMPE_AND_LIVE_PEERING=NOT_TESTED'
echo 'PEER_CUNIT_RF_OPERATION=NOT_PERFORMED'
