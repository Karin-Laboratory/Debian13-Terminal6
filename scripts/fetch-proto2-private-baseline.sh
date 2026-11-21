#!/usr/bin/env bash
# SPDX-License-Identifier: MIT
# Download only exact private archives, no image writes, no signing, no RF.
set -euo pipefail
[[ $# -eq 1 && "$1" = /* && ! -e "$1" ]] || { echo "usage: $0 /absolute/new-private-dir" >&2; exit 2; }
for tool in gh curl sha256sum unzip tar find modinfo python3; do
  command -v "$tool" >/dev/null || { echo "missing $tool" >&2; exit 2; }
done
repo=Karin-Laboratory/SBAT6A-Offline-Archive
[[ "$(gh repo view "$repo" --json isPrivate --jq .isPrivate)" == true ]] || {
  echo "Owner-private archive access required" >&2; exit 1;
}
token="$(gh auth token)"
[[ -n "$token" ]] || exit 1
dest="$1"
mkdir -m 0700 "$dest" "$dest/assets" "$dest/extracted"
download() {
  local id="$1" out="$2"
  curl --fail --silent --show-error --location \
    -H "Authorization: Bearer $token" -H "Accept: application/octet-stream" \
    "https://api.github.com/repos/$repo/releases/assets/$id" -o "$out"
}
p25="$dest/assets/P25-signed.img"
base="$dest/assets/cunit-kvm-105-kernel-modules.tar.zst"
wifi="$dest/assets/CUNIT-WIFI-KVM-P44-install.zip"
download 770875187 "$p25"
download 770074645 "$base"
download 770849098 "$wifi"
unset token
cat > "$dest/EXPECTED-SHA256SUMS" <<'SHA'
74c1c98b31cdba54f71d16f1983fbeff347bb334c5ae7d7f1353cd57f734936e  P25-signed.img
442014649e3e384535919fad40e19d2993464f20f1059c77fa4741c017a66abb  cunit-kvm-105-kernel-modules.tar.zst
3eef462793a97f9f8be14376cd05f96f6acab58049af8495f58360a10a51bdd7  CUNIT-WIFI-KVM-P44-install.zip
SHA
(cd "$dest/assets" && sha256sum -c "$dest/EXPECTED-SHA256SUMS")
[[ "$(stat -c %s "$p25")" = 33554432 ]] || exit 1
[[ "$(unzip -p "$wifi" kernel.release | tr -d '\r\n')" = 6.18.63-debian-t6-proto2 ]] || {
  echo "historical Wi-Fi pair kernel mismatch" >&2; exit 1;
}
# The earlier 105-module KVM archive does NOT contain cfg80211/mac80211.
# The independently SHA-pinned later Wi-Fi P44 ZIP does, with proto2 vermagic.
unzip -p "$wifi" modules.tar > "$dest/assets/historic-wifi-modules.tar"
if tar -tf "$dest/assets/historic-wifi-modules.tar" |
  grep -E '(^/|(^|/)\.\.(/|$))' >/dev/null; then
  echo "unsafe historical module tar path" >&2; exit 1
fi
tar -xf "$dest/assets/historic-wifi-modules.tar" \
  -C "$dest/extracted" --no-same-owner
cfg="$(find "$dest/extracted" -type f -name cfg80211.ko -print -quit)"
[[ -n "$cfg" ]] || { echo "cfg80211 missing" >&2; exit 1; }
kernel_base="$(dirname "$(dirname "$(dirname "$cfg")")")"
[[ -f "$kernel_base/net/mac80211/mac80211.ko" ]] || {
  echo "mac80211 missing" >&2; exit 1;
}
for file in "$cfg" "$kernel_base/net/mac80211/mac80211.ko"; do
  [[ "$(modinfo -F vermagic "$file")" = "6.18.63-debian-t6-proto2 SMP mod_unload aarch64" ]] || {
    echo "foreign wifi framework module $file" >&2; exit 1;
  }
done
echo PRIVATE_P25_105_AND_WIFI_BASE_ASSETS_SHA_PASS
echo "SIGNED_P25=$p25"
echo "KERNEL_BASE_TREE=$kernel_base"
echo "NO_DEVICE_WRITE_NO_SIGNING_NO_RF"
