#!/usr/bin/env bash
# SPDX-License-Identifier: MIT
# Fetch only pinned owner-private inputs; no real device, signing or publication.
set -euo pipefail
[[ $# -eq 1 && "$1" = /* && ! -e "$1" ]] || { echo "usage: $0 /absolute/new-private-dir" >&2; exit 2; }
for tool in gh sha256sum tar zstd find modinfo; do
  command -v "$tool" >/dev/null || { echo "missing tool $tool" >&2; exit 2; }
done
repo=Karin-Laboratory/SBAT6A-Offline-Archive
[[ "$(gh repo view "$repo" --json isPrivate --jq .isPrivate)" == true ]] || {
  echo "Refuse missing private GitHub access" >&2; exit 1;
}
dest="$1"
mkdir -m 0700 "$dest" "$dest/assets" "$dest/unpacked"
gh release download untagged-027373efd2705b1e227c --repo "$repo" \
  --dir "$dest/assets" --pattern 'DEBIAN13-CUNIT-420FF1B8-SIGNED-UNTESTED-p25.img'
gh release download untagged-1168670a777285d30c03 --repo "$repo" \
  --dir "$dest/assets" --pattern 'cunit-kvm-105-kernel-modules.tar.zst'
cat > "$dest/SHA256SUMS" <<'SHA'
74c1c98b31cdba54f71d16f1983fbeff347bb334c5ae7d7f1353cd57f734936e  DEBIAN13-CUNIT-420FF1B8-SIGNED-UNTESTED-p25.img
442014649e3e384535919fad40e19d2993464f20f1059c77fa4741c017a66abb  cunit-kvm-105-kernel-modules.tar.zst
SHA
(cd "$dest/assets" && sha256sum -c "$dest/SHA256SUMS")
[[ "$(wc -c <"$dest/assets/DEBIAN13-CUNIT-420FF1B8-SIGNED-UNTESTED-p25.img")" == 33554432 ]] || exit 1
archive="$dest/assets/cunit-kvm-105-kernel-modules.tar.zst"
# Reject obvious path traversal; exact source digest is checked above.
if tar --zstd -tf "$archive" | grep -E '(^/|(^|/)\.\.(/|$))' >/dev/null; then
  echo "Unsafe archive path" >&2; exit 1
fi
tar --zstd -xf "$archive" -C "$dest/unpacked" --no-same-owner
cfg=$(find "$dest/unpacked" -type f -path '*/net/wireless/cfg80211.ko' -print -quit)
[[ -n "$cfg" ]] || { echo "No cfg80211.ko in archived baseline" >&2; exit 1; }
base=$(dirname "$(dirname "$(dirname "$cfg")")")
[[ -f "$base/net/mac80211/mac80211.ko" ]] || { echo "No mac80211.ko" >&2; exit 1; }
for module in "$base/net/wireless/cfg80211.ko" "$base/net/mac80211/mac80211.ko"; do
  [[ "$(modinfo -F vermagic "$module")" == '6.18.63-debian-t6-proto2 '* ]] || {
    echo "Wrong proto2 module ABI: $module" >&2; exit 1;
  }
done
echo "PRIVATE_INPUTS_READBACK_OK"
echo "SIGNED_P25=$dest/assets/DEBIAN13-CUNIT-420FF1B8-SIGNED-UNTESTED-p25.img"
echo "KERNEL_BASE_TREE=$base"
echo "WARNING: complete module ABI/rights and actual device operation are separate gates"
