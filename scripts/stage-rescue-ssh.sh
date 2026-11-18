#!/usr/bin/env bash
# SPDX-License-Identifier: MIT
# Produce a self-contained, fail-closed ARM64 Dropbear payload for initramfs.
# Public CI does NOT supply credentials. Never publish personalized outputs.
set -euo pipefail
[[ $# = 1 && "$1" = /* && ! -e "$1" ]] || {
  echo 'usage: stage-rescue-ssh.sh /absolute/new-staging-directory' >&2; exit 2;
}
[[ "$(uname -m)" = aarch64 ]] || { echo 'Native ARM64 host required' >&2; exit 2; }
for cmd in dropbear ldd readelf cp mkdir; do command -v "$cmd" >/dev/null; done
out="$1"
umask 077
mkdir -p "$out"/{bin,sbin,etc/dropbear,root/.ssh,run,dev,proc,sys}
# Use the same known static BusyBox as the initramfs for the P44 chroot.
[[ -x /bin/busybox ]] || { echo 'busybox-static required' >&2; exit 2; }
install -m 0755 /bin/busybox "$out/bin/busybox"
for name in sh ip cat grep sleep mkdir mountpoint; do ln -s busybox "$out/bin/$name"; done
install -m 0644 "$(dirname "$0")/terminal6-rescue.service" "$out/terminal6-rescue.service"
# Single-source isolated first-boot IP; per-device private override is optional.
install -m 0644 "$(dirname "$0")/../configs/cunit-initial-management.cidr" "$out/etc/dropbear/management-ip"
binary="$(command -v dropbear)"
install -m 0755 "$binary" "$out/sbin/dropbear"
# Preserve ELF interpreter and linked shared libraries at their absolute paths.
while IFS= read -r dep; do
  [[ -f "$dep" ]] || { echo "Missing ELF library: $dep" >&2; exit 3; }
  mkdir -p "$out/${dep%/*}"
  cp -L "$dep" "$out/$dep"
done < <(
  { ldd "$binary" | awk '{for (i=1; i<=NF; ++i) if ($i ~ /^\//) print $i}';
    readelf -l "$binary" | sed -n 's/.*Requesting program interpreter: \([^]]*\)].*/\1/p'; } | sort -u
)
# Some libc builds dynamically resolve files NSS; stage it when present.
for nss in /lib/aarch64-linux-gnu/libnss_files.so.2 /usr/lib/aarch64-linux-gnu/libnss_files.so.2; do
  if [[ -f "$nss" ]]; then
    mkdir -p "$out/${nss%/*}"
    cp -L "$nss" "$out/$nss"
  fi
done
printf 'root:x:0:0:root:/root:/bin/sh\n' > "$out/etc/passwd"
printf 'root:x:0:\n' > "$out/etc/group"
printf 'passwd: files\ngroup: files\nshadow: files\n' > "$out/etc/nsswitch.conf"
install -m 0755 "$(dirname "$0")/initramfs-rescue.sh" "$out/sbin/terminal6-rescue"
# No unauthenticated login endpoint or P44 ZIP installer belongs in P25.
# No default authorized_keys, SSH host private key or root password.
# A separate owner-private process must provision both at image build time.
if [[ -n "${TERMINAL6_RESCUE_PRIVATE_DIR:-}" ]]; then
  private="$TERMINAL6_RESCUE_PRIVATE_DIR"
  [[ -d "$private" && -s "$private/authorized_keys" && -s "$private/dropbear_ed25519_host_key" ]] || {
    echo 'Private credentials absent; refusing personalization' >&2; exit 4;
  }
  grep -Eq '^ssh-ed25519 [A-Za-z0-9+/]+={0,2}( |$)' "$private/authorized_keys" || {
    echo 'Expected a valid-looking Ed25519 public key' >&2; exit 4;
  }
  install -m 0600 "$private/authorized_keys" "$out/root/.ssh/authorized_keys"
  install -m 0600 "$private/dropbear_ed25519_host_key" "$out/etc/dropbear/dropbear_ed25519_host_key"
  if [[ -f "$private/ISOLATED_MANAGEMENT_ONLY" ]]; then
    install -m 0600 "$private/ISOLATED_MANAGEMENT_ONLY" "$out/etc/dropbear/ISOLATED_MANAGEMENT_ONLY"
  fi
  if [[ -s "$private/management-ip" ]]; then
    install -m 0600 "$private/management-ip" "$out/etc/dropbear/management-ip"
  fi
  echo 'PRIVATE_RESCUE_IDENTITY_STAGED_WITHOUT_LOGGING_KEY_MATERIAL'
else
  echo 'PUBLIC_RESCUE_SSH_FAIL_CLOSED_NO_KEYS'
fi
# Reject malformed or overlapping external inputs before generating a P25.
# IP addresses can be deliberately changed for later home-LAN integration.
python3 - "$out/etc/dropbear/management-ip" <<'PY'
from ipaddress import ip_interface
from pathlib import Path
import sys
raw = Path(sys.argv[1]).read_text().strip()
iface = ip_interface(raw)
if iface.version != 4 or not (24 <= iface.network.prefixlen <= 30):
    raise SystemExit("CUNIT_INITIAL_MANAGEMENT_IP_INVALID")
print("CUNIT_INITIAL_MANAGEMENT_IP_CONFIGURED", iface)
PY
find "$out" -type f -exec chmod go-w {} +
echo 'TERMINAL6_RESCUE_DROPBEAR_ARM64_STAGED'
