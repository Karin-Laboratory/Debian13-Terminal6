#!/usr/bin/env bash
# SPDX-License-Identifier: MIT
# PRIVATE manufacture input only. Does not touch P25, P44 or a live device.
set -euo pipefail
[[ $# -eq 1 && "$1" = /* && ! -e "$1" ]] || { echo "usage: $0 /absolute/new-private-output-dir" >&2; exit 2; }
for c in gh sha256sum tar modinfo; do command -v "$c" >/dev/null || exit 2; done
repo=Karin-Laboratory/Chappie-Memory
tag=terminal6-wifi-success-20261115
kernel=6.18.63-debian-t6-proto2
[[ "$(gh repo view "$repo" --json isPrivate --jq .isPrivate)" == true ]] || { echo "private Release required" >&2; exit 1; }
out="$1"
mkdir -m 0700 "$out" "$out/download"
gh release download "$tag" --repo "$repo" --dir "$out/download" \
  --pattern 'mt76.ko' --pattern 'mt76-connac-lib.ko' --pattern 'mt7996e.ko' --pattern 'SHA256SUMS'
cat >"$out/EXPECTED-SHA256SUMS" <<'SHA'
26ffb6bd648a8fa91b424bbcf890710f8695d679d45b372e2e7ba05b68449c2f  mt76.ko
9f2df583cc73c738f7a186f1ef16faffcb6919bdf915f4ec9cf09a3df1fa05a6  mt76-connac-lib.ko
c87f66f6573d5a4c3d1e829009fc42baf3223f1b0b958c4fc8a549b135e0fecd  mt7996e.ko
SHA
cmp "$out/EXPECTED-SHA256SUMS" "$out/download/SHA256SUMS" || { echo "manifest mismatch" >&2; exit 1; }
(cd "$out/download" && sha256sum -c SHA256SUMS)
for name in mt76 mt76-connac-lib mt7996e; do
  [[ "$(modinfo -F name "$out/download/$name.ko" | tr _ -)" == "$name" ]] || exit 1
  [[ "$(modinfo -F vermagic "$out/download/$name.ko")" == "$kernel "* ]] || exit 1
done
dest="$out/stage/lib/modules/$kernel/updates/terminal6-mt76"
mkdir -p "$dest"
install -m 0600 "$out/download/"*.ko "$dest/"
cp "$out/EXPECTED-SHA256SUMS" "$dest/SHA256SUMS"
(cd "$dest" && sha256sum -c SHA256SUMS)
tar --numeric-owner --owner=0 --group=0 -cf "$out/modules.tar" -C "$out/stage" lib
sha256sum "$out/modules.tar"
echo "PRIVATE_MODULES_TAR_READY_NOT_PUBLIC_RELEASE"
