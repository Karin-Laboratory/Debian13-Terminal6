#!/bin/sh
# SPDX-License-Identifier: MIT
# Explicit interactive *first install*, never an unattended upgrade.
# Only call on an isolated cable after verifying ZIP SHA against a trusted release.
set -eu
export PATH=/bin:/sbin:/usr/bin:/usr/sbin
[ "$#" -eq 2 ] || {
    echo 'usage: terminal6-install-p44 /newroot/.terminal6/inbox/P44-install.zip EXPECTED_SHA256' >&2
    exit 2
}
archive="$1"
expected="$2"
root=/newroot
inbox="$root/.terminal6/inbox"
case "$expected" in *[!0-9a-f]*|'') echo EXPECTED_SHA256_INVALID; exit 2;; esac
[ "$(printf %s "$expected" | wc -c)" -eq 64 ] || exit 2
[ -f "$archive" ] && [ ! -L "$archive" ] || exit 2
case "$archive" in "$inbox"/*) ;; *) echo ARCHIVE_MUST_BE_IN_P44_INBOX; exit 2;; esac
# Reuse the strictly blank-P44 gate; NEVER overwrite installed user data.
terminal6-firstboot probe || { echo CUNIT_INSTALL_REJECT_NONEMPTY_P44; exit 1; }
actual="$(sha256sum "$archive" | awk '{print $1}')"
[ "$actual" = "$expected" ] || { echo CUNIT_INSTALL_ZIP_DIGEST_MISMATCH; exit 1; }
[ ! -e "$inbox/rootfs.tar.gz" ] || { echo CUNIT_INSTALL_REFUSE_EXISTING_STAGING; exit 1; }
[ ! -e "$inbox/modules.tar" ] || exit 1
# Extract known filenames only, never arbitrary ZIP paths to the root filesystem.
for file in rootfs.tar.gz modules.tar SHA256SUMS kernel.release manifest.json; do
    unzip -p "$archive" "$file" > "$inbox/$file" || exit 1
    [ -s "$inbox/$file" ] || exit 1
done
(cd "$inbox" && sha256sum -c SHA256SUMS) || {
    echo CUNIT_INSTALL_INTERNAL_SHA_MISMATCH; exit 1;
}
running="$(uname -r)"
expected_release="$(cat "$inbox/kernel.release")"
[ "$running" = "$expected_release" ] || {
    echo CUNIT_INSTALL_MODULE_ABI_RELEASE_MISMATCH
    exit 1
}
echo 'CUNIT_INSTALL_VALIDATED_ZIP_AND_MATCHING_KERNEL'
# No mkfs, no partition table/bootcontrol operation; extraction is confined
# to the previously confirmed empty ext4 rootfs_data.
tar xzpf "$inbox/rootfs.tar.gz" -C "$root" || {
    echo CUNIT_INSTALL_INTERRUPTED_UART_RECOVERY_REQUIRED; exit 1;
}
tar xpf "$inbox/modules.tar" -C "$root" || {
    echo CUNIT_INSTALL_MODULE_EXTRACTION_FAILED_UART_RECOVERY_REQUIRED; exit 1;
}
[ -x "$root/sbin/init" ] && [ -x "$root/usr/bin/dropbearconvert" ] || {
    echo CUNIT_INSTALL_ROOTFS_INCOMPLETE; exit 1;
}
[ -s "$root/.terminal6/ssh/dropbear_ed25519_host_key" ] || exit 1
# Preserve the device-generated firstboot host identity across Debian handoff.
chroot "$root" /usr/bin/dropbearconvert dropbear openssh \
    /.terminal6/ssh/dropbear_ed25519_host_key /etc/ssh/ssh_host_ed25519_key || exit 1
chmod 0600 "$root/etc/ssh/ssh_host_ed25519_key"
chroot "$root" /usr/bin/ssh-keygen -lf /etc/ssh/ssh_host_ed25519_key || exit 1
sync
echo 'CUNIT_P44_INSTALLED_AUTH_NOT_CONFIGURED'
echo 'NEXT: terminal6-firstboot passwd OR copy your public key to /newroot/root/.ssh/authorized_keys'
echo 'NEXT: verify P44 credentials, then terminal6-firstboot finalize; NEVER leave isolated link attached to home LAN'
