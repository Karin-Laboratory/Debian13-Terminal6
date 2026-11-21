#!/bin/sh
# SPDX-License-Identifier: MIT
# Terminal 6 P44 only: each unit supplies its own stock EEPROM and OTP.
set -eu
PATH=/usr/sbin:/usr/bin:/sbin:/bin
export PATH
umask 077
kernel=6.18.63-debian-t6-proto2
mods=/lib/modules/$kernel/updates/terminal6-mt76
work=/run/terminal6-proto2-wifi
target=/lib/firmware/mediatek/mt7996
log() { logger -t terminal6-proto2-wifi -- "$*" 2>/dev/null || :; echo "$*" >&2; }
fail() { log "FAIL=$1"; exit 1; }
part() {
  wanted=$1; found=; count=0
  for event in /sys/class/block/*/uevent; do
    [ -r "$event" ] || continue
    grep -qx "PARTNAME=$wanted" "$event" || continue
    dev=$(sed -n 's/^DEVNAME=//p' "$event")
    [ -n "$dev" ] || fail MISSING_DEVNAME
    found=/dev/$dev; count=$((count+1))
  done
  [ "$count" -eq 1 ] || fail "PART_COUNT_$wanted"
  [ -b "$found" ] || fail NOT_BLOCK
  printf '%s\n' "$found"
}
mounted() { awk -v p="$1" '$2==p {yes=1} END {exit !yes}' /proc/mounts; }
[ "$(id -u)" = 0 ] || fail NOT_ROOT
[ "$(uname -r)" = "$kernel" ] || fail WRONG_KERNEL
grep -Eq '(^|[[:space:]])bootslot=a([[:space:]]|$)' /proc/cmdline || fail NOT_SLOT_A
[ "$(stat -f -c %T /run)" = tmpfs ] || fail RUN_NOT_TMPFS
root=$(part rootfs_data)
[ "$(readlink -f "$(findmnt -n -o SOURCE /)")" = "$(readlink -f "$root")" ] || fail NOT_P44
[ "$(findmnt -n -o FSTYPE /)" = ext4 ] || fail ROOT_NOT_EXT4
set -- /sys/class/ieee80211/phy*
[ "$#" -eq 1 ] && [ -d "$1" ] && { log PHY_ALREADY_PRESENT; exit 0; }
grep -q '^mt7996e ' /proc/modules && fail DRIVER_ALREADY_LOADED_WITHOUT_PHY
grep -q '^mt76 ' /proc/modules && fail MT76_PRELOADED
grep -q '^mt76_connac_lib ' /proc/modules && fail CONNAC_PRELOADED
[ -d "$mods" ] || fail MODULE_DIR_MISSING
[ -f "$mods/SHA256SUMS" ] || fail MODULE_MANIFEST_MISSING
(cd "$mods" && sha256sum -c SHA256SUMS) >/dev/null || fail MODULE_SHA
for name in mt76 mt76-connac-lib mt7996e; do
  [ -f "$mods/$name.ko" ] && [ ! -L "$mods/$name.ko" ] || fail MODULE_MISSING
done

mkdir -p "$work"; chmod 0700 "$work"
mkdir "$work/attempt" 2>/dev/null || fail ALREADY_ATTEMPTED_THIS_BOOT
mkdir -m 0700 "$work/p26" "$work/stock" "$work/firmware"
p26=$work/p26; stock=$work/stock; stage=$work/firmware
cleanup() {
  mounted "$stock" && umount "$stock" || :
  mounted "$p26" && umount "$p26" || :
}
trap cleanup EXIT HUP INT TERM
mount -t squashfs -o ro "$(part rootfs_a)" "$p26" || fail ROOTFS_A_RO_MOUNT
mount -t squashfs -o ro "$(part rootfs_b)" "$stock" || fail ROOTFS_B_RO_MOUNT
oem=$stock/lib/firmware/MT7990_EEPROM.bin
[ -f "$oem" ] && [ ! -L "$oem" ] || fail OWN_EEPROM_MISSING
[ "$(wc -c < "$oem" | tr -d ' ')" = 7680 ] || fail OWN_EEPROM_SIZE
[ "$(od -An -N2 -tx1 "$oem" | tr -d ' \n')" = 9079 ] || fail OWN_EEPROM_ID
src=$p26/lib/firmware/mediatek/mt7996
[ -d "$src" ] && [ ! -L "$src" ] || fail OWN_P26_FIRMWARE_DIR
for pair in \
  mt7996_wa_mt6990.bin:mt7996_wa.bin \
  mt7996_wm_mt6990.bin:mt7996_wm.bin \
  mt7996_dsp_mt6990.bin:mt7996_dsp.bin \
  mt7996_rom_patch_mt6990.bin:mt7996_rom_patch.bin; do
    old=$(printf %s "$pair" | cut -d: -f1)
    new=$(printf %s "$pair" | cut -d: -f2)
    [ -f "$src/$old" ] && [ ! -L "$src/$old" ] && [ -s "$src/$old" ] || fail P26_FIRMWARE_MISSING
    cp "$src/$old" "$stage/$new" || fail FIRMWARE_STAGE
    case "$new" in
      mt7996_wa.bin|mt7996_wm.bin|mt7996_rom_patch.bin)
        alias=$(printf %s "$new" | sed 's/\.bin$/_233.bin/')
        cp "$stage/$new" "$stage/$alias" || fail FIRMWARE_VARIANT_STAGE ;;
    esac
done
for name in mt7996_eeprom.bin mt7996_eeprom_2i5i6i.bin \
  mt7996_eeprom_233_2i5i6i.bin mt7990_eeprom.bin mt7990_eeprom_2i5i.bin; do
  cp "$oem" "$stage/$name" || fail EEPROM_STAGE
done
chmod 0600 "$stage"/*
umount "$stock" || fail STOCK_UNMOUNT
umount "$p26" || fail P26_UNMOUNT
trap - EXIT HUP INT TERM

# A RAM bind covers existing P44 firmware WITHOUT deleting original files.
[ -d "$target" ] && [ ! -L "$target" ] || fail FIRMWARE_TARGET_INVALID
mounted "$target" && fail FIRMWARE_ALREADY_MOUNTED
mount --bind "$stage" "$target" || fail FIRMWARE_RAM_BIND
modprobe cfg80211 || fail CFG80211_LOAD
modprobe mac80211 || fail MAC80211_LOAD
insmod "$mods/mt76.ko" || fail MT76_LOAD
insmod "$mods/mt76-connac-lib.ko" || fail CONNAC_LOAD
insmod "$mods/mt7996e.ko" || fail MT7996_LOAD
count=0
while [ "$count" -lt 60 ]; do
  set -- /sys/class/ieee80211/phy*
  [ "$#" -eq 1 ] && [ -d "$1" ] && { log "PHY_REGISTERED_FROM_OWN_EEPROM"; exit 0; }
  sleep 1; count=$((count+1))
done
fail PHY_NOT_REGISTERED
