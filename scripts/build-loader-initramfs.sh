#!/usr/bin/env bash
# SPDX-License-Identifier: MIT
# Native ARM64, from public source and system OSS packages. No signer/device.
set -euo pipefail
[[ $# = 1 && "$1" = /* && ! -e "$1" ]] || { echo 'usage: build-loader-initramfs.sh /absolute/new-file.cpio.gz' >&2; exit 2; }
[[ "$(uname -m)" = aarch64 ]] || { echo 'Native ARM64 required' >&2; exit 2; }
for cmd in ldd readelf cpio sha256sum gzip busybox dropbear dropbearkey kexec blkid mountpoint; do
  command -v "$cmd" >/dev/null || { echo "Missing host dependency: $cmd" >&2; exit 2; }
done
root="$(cd "$(dirname "$0")/.." && pwd)"
tmp="$(mktemp -d)"
trap 'rm -rf -- "$tmp"' EXIT
umask 077
mkdir -p "$tmp"/{bin,sbin,etc/dropbear,root/.ssh,run,config,userdata,dev/pts,proc,sys}
install -m 0755 /bin/busybox "$tmp/bin/busybox"
for name in sh ash mount umount cat grep sed ip sleep ls mkdir cp rm ln chmod sync printf sha256sum stat test reboot passwd touch; do
  ln -s busybox "$tmp/bin/$name"
done
# A distro's busybox-static may NOT compile blkid/mountpoint. They must
# be real util-linux ARM64 executables rather than dead BusyBox symlinks.
for applet in sh ash mount umount cat grep sed ip sleep ls mkdir cp rm ln chmod sync printf sha256sum stat test reboot passwd touch; do
  if ! /bin/busybox --list | grep -qx "$applet"; then
    echo "INITRAMFS_REQUIRED_BUSYBOX_APPLET_MISSING: $applet" >&2
    exit 42
  fi
done
install -m 0755 "$root/initramfs/loader-init" "$tmp/init"
install -m 0755 "$root/initramfs/terminal6-boot" "$tmp/sbin/terminal6-boot"
for program in dropbear dropbearkey kexec blkid mountpoint; do
  exe="$(command -v "$program")"
  install -m 0755 "$exe" "$tmp/sbin/$program"
  # Collect direct and transitive dynamic closure, including ARM64 ELF interpreter.
  if ldd "$exe" 2>&1 | grep -q 'not found'; then
    echo "INITRAMFS_MISSING_HOST_ELF_DEPENDENCY: $program" >&2; exit 42
  fi
  while IFS= read -r dep; do
    [[ "$dep" = /* && -f "$dep" ]] || { echo "Bad ELF dependency: $dep" >&2; exit 2; }
    mkdir -p "$tmp/${dep%/*}"
    cp -L "$dep" "$tmp/$dep"
  done < <(
    { ldd "$exe" | awk '{for(i=1;i<=NF;i++) if($i ~ /^\//) print $i}';
      readelf -l "$exe" | sed -n 's/.*Requesting program interpreter: \([^]]*\)].*/\1/p'; } | sort -u
  )
done
# Assert util-linux binaries are real commands rather than dead BusyBox links.
for tool in blkid mountpoint; do
  test -x "$tmp/sbin/$tool" && test ! -L "$tmp/sbin/$tool" || {
    echo "INITRAMFS_REAL_UTIL_LINUX_MISSING: $tool" >&2; exit 42;
  }
done
for nss in /lib/aarch64-linux-gnu/libnss_files.so.2 /usr/lib/aarch64-linux-gnu/libnss_files.so.2; do
  if [[ -f "$nss" ]]; then mkdir -p "$tmp/${nss%/*}"; cp -L "$nss" "$tmp/$nss"; fi
done
printf 'root:x:0:0:root:/root:/bin/sh\n' > "$tmp/etc/passwd"
printf 'root::0:0:99999:7:::\n' > "$tmp/etc/shadow"
printf 'root:x:0:\n' > "$tmp/etc/group"
printf 'passwd: files\ngroup: files\nshadow: files\n' > "$tmp/etc/nsswitch.conf"
chmod 600 "$tmp/etc/shadow"
# No shared host private key or credentials. Device generates on firstboot.
test ! -e "$tmp/etc/dropbear/dropbear_ed25519_host_key"
test ! -e "$tmp/root/.ssh/authorized_keys"
# Stable reproducible file metadata, deterministic gzip. Compare a second build in CI.
find "$tmp" -print0 | xargs -0 -r touch -h -d "@${SOURCE_DATE_EPOCH:-0}"
(cd "$tmp" && find . -print0 | LC_ALL=C sort -z |
  cpio --null -o -H newc --quiet --owner=0:0 --reproducible | gzip -n -9) > "$1"
gzip -t "$1"
size="$(stat -c %s "$1")"
test "$size" -lt 12000000 || { echo "Initramfs too large: $size" >&2; exit 1; }
echo "TERMINAL6_MINIMAL_INITRAMFS_BUILT bytes=$size sha=$(sha256sum "$1")"
