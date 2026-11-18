#!/usr/bin/env bash
# SPDX-License-Identifier: MIT
# Create a PUBLIC Debian 13 arm64 P44 rootfs archive, never touch a block device.
# Usage on Debian arm64: sudo bash scripts/build-public-p44-rootfs.sh /absolute/NEW-output-dir [authorized_keys]
set -euo pipefail
[[ $# -eq 1 || $# -eq 2 ]] || { echo "usage: $0 /absolute/new-output-dir [authorized_keys]" >&2; exit 2; }
dest="$1"
[[ "$dest" = /* && "$dest" != / && ! -e "$dest" && ! -L "$dest" ]] || exit 2
[[ "$(id -u)" = 0 ]] || { echo "Run as root on a disposable ARM64 build VM" >&2; exit 2; }
[[ "$(uname -m)" = aarch64 ]] || { echo "Native ARM64 Linux builder required" >&2; exit 2; }
for tool in debootstrap chroot systemctl tar sha256sum dpkg-query ssh-keygen; do
  command -v "$tool" >/dev/null || { echo "missing host tool $tool" >&2; exit 2; }
done
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
auth=""
if [[ $# -eq 2 ]]; then
  auth="$2"
  [[ "$auth" = /* && -f "$auth" && ! -L "$auth" ]] || exit 2
  [[ "$(wc -c <"$auth")" -le 65536 ]] || { echo "authorized_keys too large" >&2; exit 2; }
  [[ -s "$auth" ]] || { echo "authorized_keys empty" >&2; exit 2; }
  ssh-keygen -lf "$auth" >/dev/null
fi
mkdir -m 0700 "$dest"
out="$dest/rootfs"
# No private firmware, templates, host keys, passwords, device serials or
# calibration. This archive is a portable ROOTFS, not a signed/bootable P25.
debootstrap --arch=arm64 --variant=minbase \
  --include=systemd-sysv,systemd-resolved,openssh-server,openssh-client,dropbear-bin,iproute2,udev,kmod,ca-certificates,iputils-ping,dbus \
  trixie "$out" https://deb.debian.org/debian
printf '%s\n' terminal6-debian > "$out/etc/hostname"
cat > "$out/etc/fstab" <<'FSTAB'
PARTLABEL=rootfs_data  /  ext4  defaults,noatime  0  1
FSTAB
mkdir -p "$out/etc/systemd/network" "$out/etc/ssh/sshd_config.d"
cat > "$out/etc/systemd/network/20-terminal6-lan2.network" <<'NET'
[Match]
Name=lan2

[Network]
Address=192.168.1.1/24
DHCP=no
IPv6AcceptRA=no
LinkLocalAddressing=no
NET
ln -sfn ../run/systemd/resolve/stub-resolv.conf "$out/etc/resolv.conf"
cat > "$out/etc/ssh/sshd_config.d/60-terminal6-secure.conf" <<'SSH'
PasswordAuthentication yes
KbdInteractiveAuthentication no
PermitRootLogin yes
PermitEmptyPasswords no
PubkeyAuthentication yes
SSH
if [[ -n "$auth" ]]; then
  install -d -m 0700 "$out/root/.ssh"
  install -m 0600 "$auth" "$out/root/.ssh/authorized_keys"
fi
# Debian's openssh-server can generate host keys during bootstrap; scrub
# these so every actual device creates its *own* keys after boot.
find "$out/etc/ssh" -maxdepth 1 -type f -name 'ssh_host_*' -delete
cat > "$out/etc/systemd/system/terminal6-ssh-hostkeys.service" <<'UNIT'
[Unit]
Description=Generate unique SSH host keys on first Debian boot
After=local-fs.target
Before=ssh.service
ConditionPathExists=!/etc/ssh/ssh_host_ed25519_key

[Service]
Type=oneshot
ExecStart=/usr/bin/ssh-keygen -A
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
UNIT
# Install the public netlink-only LAN readiness helper. Never install the
# owner-private test23/test24 module loader from scripts/start-management.sh.
install -m 0755 "$root/public-management/start-management.sh" \
  "$out/usr/local/sbin/terminal6-public-management"
cat > "$out/etc/systemd/system/terminal6-public-management.service" <<'UNIT'
[Unit]
Description=Public MT6990 NETSYS and MT7531 LAN readiness
After=systemd-udevd.service
Before=systemd-networkd.service ssh.service

[Service]
Type=oneshot
ExecStart=/usr/local/sbin/terminal6-public-management
RemainAfterExit=yes
TimeoutStartSec=45
StandardOutput=journal+console

[Install]
WantedBy=multi-user.target
UNIT
chroot "$out" /usr/bin/passwd -l root >/dev/null
for service in systemd-networkd.service systemd-resolved.service ssh.service terminal6-ssh-hostkeys.service terminal6-public-management.service; do
  systemctl --root="$out" enable "$service" >/dev/null
done
if mountpoint -q "$out/proc" || mountpoint -q "$out/sys" || mountpoint -q "$out/dev"; then
  echo "Refusing archive while bootstrap mounts exist" >&2
  exit 1
fi
chroot "$out" /usr/bin/dpkg-query -W -f='${Package} ${Version} ${Architecture}\n' \
  > "$dest/debian-package-manifest.txt"
test -s "$dest/debian-package-manifest.txt" || { echo "empty Debian package manifest" >&2; exit 1; }
(cd "$out" && tar --numeric-owner --sort=name --xattrs --xattrs-include='*' --acls -czf "$dest/debian13-p44-rootfs.tar.gz" .)
sha256sum "$dest/debian13-p44-rootfs.tar.gz" "$dest/debian-package-manifest.txt" \
  > "$dest/SHA256SUMS"
cat > "$dest/STATUS.txt" <<'STATUS'
PUBLIC_DEBIAN13_ARM64_ROOTFS_ARCHIVE_ONLY
NO_RAW_PARTITION_WRITE
NO_SIGNING_OR_BOOT_PROOF
NO_PRESET_SSH_HOST_KEY_OR_PASSWORD
PASSWORD_AUTH_ONLY_AFTER_EXPLICIT_PASSWORD_SET_IN_P44
NO_EMPTY_PASSWORD_ON_NORMAL_SSH
NETWORK_STATIC_192_168_1_1_ON_LAN2_REQUIRES_HARDWARE_PROOF
STATUS
echo PUBLIC_P44_ROOTFS_ARCHIVE_BUILT_NOT_DEVICE_BOOT_VALIDATED
