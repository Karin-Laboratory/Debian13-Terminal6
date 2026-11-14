#!/bin/sh
# SPDX-License-Identifier: MIT
# Origin: independently authored read-only API inventory, 2026-11-14.
# Run via SSH stdin; redirect stdout on the development VM, never on P44.
# Output is PRIVATE pending review. No scan, module load, reset or GPIO writes.
set -u
export LC_ALL=C PYTHONDONTWRITEBYTECODE=1
for query in 'lscpu' 'lspci -nnk' 'lsusb -t' 'iw phy' 'iw dev' 'iw reg get' \
  'rfkill list' 'btmgmt info' 'i2cdetect -l' 'gpiodetect' 'gpioinfo' \
  'ethtool lan2' 'ethtool -i lan2' 'ethtool -S lan2' 'ethtool -k lan2' \
  'ethtool -i eth1' 'ethtool -S eth1' 'ethtool lan3'; do
    printf '\n### %s\n' "$query"
    timeout 8 sh -c "$query"
    printf 'RC=%s\n' "$?"
done
# Deliberately no generic i2cdetect scan, arbitrary /dev reads, watchdog open,
# full debugfs scrape, EXT_CSD writes or AT commands. See separate AT allowlist.
