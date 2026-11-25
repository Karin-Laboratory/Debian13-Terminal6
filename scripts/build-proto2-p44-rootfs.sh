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
  --include=systemd-sysv,systemd-resolved,iw,openssh-server,openssh-client,iproute2,udev,kmod,ca-certificates,iputils-ping,dbus,util-linux,python3-minimal,wireless-regdb \
  trixie "$out" https://deb.debian.org/debian
printf '%s\n' terminal6-debian > "$out/etc/hostname"
cat > "$out/etc/fstab" <<'FSTAB'
PARTLABEL=rootfs_data  /  ext4  defaults,noatime  0  1
FSTAB
mkdir -p "$out/etc/systemd/network" "$out/etc/ssh/sshd_config.d"
install -m 0644 "$root"/network/p44/* "$out/etc/systemd/network/"
ln -sfn ../run/systemd/resolve/stub-resolv.conf "$out/etc/resolv.conf"
cat > "$out/etc/ssh/sshd_config.d/00-terminal6-secure.conf" <<'SSH'
ListenAddress 192.168.1.1
Port 22
PasswordAuthentication no
KbdInteractiveAuthentication no
PermitRootLogin no
PermitEmptyPasswords no
PubkeyAuthentication yes
AuthenticationMethods publickey
DisableForwarding yes
SSH
# No automatic bootstrap listener. The temporary non-root password flow is
# a separate acceptance gate; this candidate is not a device install.
install -m 0755 "$root/scripts/p44-firstboot.sh" "$out/usr/local/sbin/terminal6-p44-firstboot"
mkdir -p "$out/etc/systemd/system" "$out/var/lib/terminal6" "$out/run/sshd"
chroot "$out" /usr/bin/passwd -l root >/dev/null
chroot "$out" /usr/bin/ssh-keygen -A
chroot "$out" /usr/local/sbin/terminal6-p44-firstboot check > "$dest/p44-sshd-policy.txt"
# Parse the isolated onboarding policy with the target sshd. These fixtures
# are removed before packaging. No account, unit, or listener is created.
install -m 0600 "$root/tests/fixtures/p44-bootstrap-sshd.conf" "$out/run/t6-bootstrap-ci.conf"
install -m 0700 "$root/tests/fixtures/p44-bootstrap-sshd-check.sh" "$out/run/t6-bootstrap-ci.sh"
chroot "$out" /bin/sh /run/t6-bootstrap-ci.sh /run/t6-bootstrap-ci.conf \
  | tee "$dest/p44-bootstrap-sshd-policy.txt"
install -m 0600 "$root/scripts/p44-bootstrap-preflight.py" "$out/run/t6-bootstrap-preflight-ci.py"
install -m 0600 "$root/tests/fixtures/test-p44-bootstrap-preflight.py" "$out/run/t6-bootstrap-preflight-tests.py"
chroot "$out" /usr/bin/python3 -B /run/t6-bootstrap-preflight-tests.py /run/t6-bootstrap-preflight-ci.py
rm -f -- "$out/run/t6-bootstrap-ci.conf" "$out/run/t6-bootstrap-ci.sh" \
  "$out/run/t6-bootstrap-preflight-ci.py" "$out/run/t6-bootstrap-preflight-tests.py"
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
if ! chroot "$out" /usr/lib/systemd/systemd --version > "$dest/p44-init-version.txt" 2>&1; then
  echo "P44_INIT_CHROOT_EXEC_FAILED (native disposable runner)" >&2
  sed -n "1,12p" "$dest/p44-init-version.txt" >&2
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
# Never leave OpenSSH's socket activation enabled in this initial image.
systemctl --root="$out" disable ssh.service ssh.socket >/dev/null
systemctl --root="$out" mask ssh.socket >/dev/null
for service in systemd-networkd.service systemd-resolved.service terminal6-ssh-hostkeys.service terminal6-proto2-wifi.service; do
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
ROOT_PASSWORD_LOCKED_NO_PRESET_SSH_HOST_KEY
P44_EFFECTIVE_SSHD_POLICY_CHECKED
P44_BOOTSTRAP_POLICY_OFFLINE_ONLY_NO_RUNTIME_ACCEPTANCE
SSH_DISABLED_PENDING_PROVISIONING_TEMP_PASSWORD_NOT_IMPLEMENTED_DO_NOT_INSTALL
NETWORK_STATIC_192_168_1_1_ON_BR_LAN_REQUIRES_HARDWARE_PROOF
STATUS
echo PUBLIC_P44_ROOTFS_ARCHIVE_BUILT_NOT_DEVICE_BOOT_VALIDATED
