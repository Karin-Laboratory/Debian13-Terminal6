#!/usr/bin/env bash
# SPDX-License-Identifier: MIT
# Create an OWNER-NEUTRAL proto2 Debian 13 arm64 P44 rootfs archive, never touch a block device.
# Usage on Debian arm64: sudo bash scripts/build-proto2-p44-rootfs.sh /absolute/NEW-output-dir
set -euo pipefail
[[ $# -eq 1 ]] || { echo "usage: $0 /absolute/new-output-dir" >&2; exit 2; }
dest="$1"
[[ "$dest" = /* && "$dest" != / && ! -e "$dest" && ! -L "$dest" ]] || exit 2
[[ "$(id -u)" = 0 ]] || { echo "Run as root on a disposable ARM64 build VM" >&2; exit 2; }
[[ "$(uname -m)" = aarch64 ]] || { echo "Native ARM64 Linux builder required" >&2; exit 2; }
for tool in debootstrap chroot systemctl tar sha256sum dpkg-query ssh-keygen; do
  command -v "$tool" >/dev/null || { echo "missing host tool $tool" >&2; exit 2; }
done
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
mkdir -m 0700 "$dest"
out="$dest/rootfs"
# No private firmware, templates, host keys, passwords, device serials or
# calibration. This archive is a portable ROOTFS, not a signed/bootable P25.
debootstrap --arch=arm64 --variant=minbase \
  --include=systemd-sysv,systemd-resolved,iw,openssh-server,openssh-client,dropbear-bin,iproute2,udev,kmod,ca-certificates,iputils-ping,dbus,util-linux,python3-minimal,wireless-regdb \
  trixie "$out" https://deb.debian.org/debian
printf '%s\n' terminal6-debian > "$out/etc/hostname"
cat > "$out/etc/fstab" <<'FSTAB'
PARTLABEL=rootfs_data  /  ext4  defaults,noatime  0  1
FSTAB
mkdir -p "$out/etc/systemd/network" "$out/etc/ssh/sshd_config.d"
cat > "$out/etc/systemd/network/10-terminal6-lan2.network" <<'NET'
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
# Firstboot setup is DEBIAN P44 ONLY.  SSH server auth transitions after
# the owner creates a root password or public key and tests a second login.
# Dropbear -B allows empty-password root only on the physical isolated LAN,
# and systemd starts normal OpenSSH only after firstboot-finalize.
install -m 0755 "$root/scripts/p44-firstboot.sh" "$out/usr/local/sbin/terminal6-p44-firstboot"
mkdir -p "$out/etc/systemd/system" "$out/etc/dropbear" "$out/var/lib/terminal6"
cat > "$out/etc/systemd/system/terminal6-firstboot.service" <<'UNIT'
[Unit]
Description=Isolated C-unit initial Debian P44 root SSH provisioning ONLY
After=systemd-networkd.service terminal6-ssh-hostkeys.service
Requires=systemd-networkd.service
ConditionPathExists=!/var/lib/terminal6/firstboot-complete
Before=ssh.service

[Service]
Type=simple
ExecStartPre=/usr/local/sbin/terminal6-p44-firstboot prepare
ExecStart=/usr/sbin/dropbear -F -E -B -j -k -r /etc/dropbear/dropbear_ed25519_host_key -p 192.168.1.1:22
# Preserve the active management child session when the listener closes.
KillMode=process
TimeoutStopSec=10
Restart=on-failure
StandardOutput=journal+console
StandardError=journal+console

[Install]
WantedBy=multi-user.target
UNIT
cat > "$out/etc/systemd/system/terminal6-authcheck.service" <<'UNIT'
[Unit]
Description=Temporary authenticated Debian SSH session verification (port 2223)
After=systemd-networkd.service terminal6-ssh-hostkeys.service
ConditionPathExists=!/var/lib/terminal6/firstboot-complete

[Service]
Type=simple
ExecStartPre=/usr/bin/mkdir -p /run/sshd
ExecStart=/usr/sbin/sshd -D -e -p 2223 -o ListenAddress=192.168.1.1 -o PermitRootLogin=yes -o PermitEmptyPasswords=no -o PasswordAuthentication=yes -o KbdInteractiveAuthentication=no
KillMode=process

[Install]
# Not enabled at boot: explicitly started by terminal6-p44-firstboot verify-start
WantedBy=multi-user.target
UNIT
# If this rootfs gets deployed into an existing partition, the manual Method B
# instructions must reject overwrite. A fresh archive has NO finished marker.
test ! -e "$out/var/lib/terminal6/firstboot-complete"
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
# A single isolated LAN is a human prerequisite. Normal ssh.service may
# start only AFTER the completed marker exists, never during empty-root setup.
mkdir -p "$out/etc/systemd/system/ssh.service.d" "$out/etc/modprobe.d"
cat > "$out/etc/systemd/system/ssh.service.d/10-terminal6-provisioned.conf" <<'UNIT'
[Unit]
ConditionPathExists=/var/lib/terminal6/firstboot-complete
UNIT

# Prevent modalias/udev loading the MT7996 PCI driver before this
# unit has mounted THIS unit's OEM EEPROM/firmware in RAM.
cat > "$out/etc/modprobe.d/terminal6-proto2-wifi.conf" <<'MOD'
blacklist mt7996e
MOD
install -m 0755 "$root/scripts/proto2-wifi-start.sh" \
  "$out/usr/local/sbin/terminal6-proto2-wifi-start"
mkdir -p "$out/lib/firmware/mediatek/mt7996"
cat > "$out/etc/systemd/system/terminal6-proto2-wifi.service" <<'UNIT'
[Unit]
Description=Terminal 6 proto2 per-unit EEPROM/OTP Wi-Fi PHY only
After=local-fs.target systemd-udevd.service
ConditionKernelVersion=6.18.63-debian-t6-proto2

[Service]
Type=oneshot
ExecStart=/usr/local/sbin/terminal6-proto2-wifi-start
RemainAfterExit=yes
TimeoutStartSec=120s
StandardOutput=journal+console
StandardError=journal+console

[Install]
WantedBy=multi-user.target
UNIT
# NOT enabled on fresh installs. An owner must separately authorize the
# C-unit's misc operation after acceptance; this never changes stock B.
install -m 0755 "$root/scripts/proto2-slot-a-success.py" \
  "$out/usr/local/sbin/terminal6-proto2-slot-a-success"
mkdir -p -m 0700 "$out/etc/terminal6"
cat > "$out/etc/systemd/system/terminal6-slot-a-success.service" <<'UNIT'
[Unit]
Description=Mark validated C-unit Debian slot A successful (stock B preserved)
After=local-fs.target systemd-networkd.service ssh.service terminal6-proto2-wifi.service
ConditionPathExists=/var/lib/terminal6/firstboot-complete
ConditionPathExists=/etc/terminal6/authorize-slot-a-success
ConditionKernelVersion=6.18.63-debian-t6-proto2

[Service]
Type=oneshot
ExecStart=/usr/local/sbin/terminal6-proto2-slot-a-success --commit
Restart=no
StandardOutput=journal+console
StandardError=journal+console

[Install]
WantedBy=multi-user.target
UNIT

# Fail closed if the *actual native ARM64 rootfs* cannot exec its own init.
# The P25 initramfs uses /sbin/init after switch_root; a missing merged-/usr
# link, ELF interpreter, or dynamic library would otherwise panic PID 1.
# "--version" is intentionally NOT a PID 1 boot; this is only an ABI gate.
if [[ ! -x "$out/usr/lib/systemd/systemd" || ! -L "$out/sbin" || ! -L "$out/usr/sbin/init" ]]; then
  echo "P44_INIT_MERGED_USR_SYMLINK_OR_EXEC_MISSING" >&2
  exit 1
fi
if ! chroot "$out" /sbin/init --version > "$dest/p44-init-version.txt" 2>&1; then
  echo "P44_INIT_CHROOT_EXEC_FAILED (inspect p44-init-version.txt privately)" >&2
  exit 1
fi
grep -q '^systemd ' "$dest/p44-init-version.txt" || {
  echo "P44_INIT_CHROOT_WRONG_OUTPUT" >&2
  exit 1
}
echo "P44_INIT_NATIVE_ARM64_CHROOT_EXEC_PASS"

# Do not ship builder machine identity or dbus machine identifier.
: > "$out/etc/machine-id"
rm -f "$out/var/lib/dbus/machine-id"
mkdir -p "$out/var/lib/dbus"
ln -s /etc/machine-id "$out/var/lib/dbus/machine-id"
# OWNER-APPROVED EXCEPTION: only Debian firstboot Dropbear on 192.168.1.1:22
# may accept an empty root password; normal OpenSSH uses PermitEmptyPasswords no.
chroot "$out" /usr/bin/passwd -d root >/dev/null
# Never leave OpenSSH's socket activation enabled in this initial image.
systemctl --root="$out" disable ssh.service ssh.socket >/dev/null 2>&1 || true
systemctl --root="$out" mask ssh.socket >/dev/null 2>&1 || true
for service in systemd-networkd.service systemd-resolved.service terminal6-firstboot.service terminal6-ssh-hostkeys.service terminal6-proto2-wifi.service; do
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
NO_PRESET_SSH_HOST_KEY; FIRSTBOOT_ROOT_BLANK_PASSWORD_ISOLATED_EXCEPTION
FIRSTBOOT_DROPBEAR_TCP22_DISABLED_AFTER_P44_AUTHENTICATED_SECOND_SESSION
NO_EMPTY_PASSWORD_ON_NORMAL_OPENSSH
NETWORK_STATIC_192_168_1_1_ON_LAN2_REQUIRES_HARDWARE_PROOF
STATUS
echo PUBLIC_P44_ROOTFS_ARCHIVE_BUILT_NOT_DEVICE_BOOT_VALIDATED
