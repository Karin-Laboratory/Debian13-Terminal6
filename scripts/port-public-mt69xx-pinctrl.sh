#!/usr/bin/env bash
# SPDX-License-Identifier: MIT
# Reuse GPL-2.0 MT69xx Paris pinctrl provider from pinned public OSS sources.
# Called from build-linux-6.18.sh only on explicit opt-in, before Kconfig.
set -euo pipefail
test "$#" = 1
tree="$1"
test -d "$tree/.git"
for bin in curl git sha256sum; do command -v "$bin" >/dev/null; done
source_commit=a40df9a5afb46716dea799acea69f17480df4d82
source_repo='13179415360/openwrt-mt6990-lg6851f'
patch_path='target/linux/mediatek/patches-6.18'
tmp=$(mktemp -d)
trap 'rm -rf -- "$tmp"' EXIT
while IFS=' ' read -r name blob_sha; do
  test -n "$name" || continue
  curl --fail --location --silent --show-error --retry 3 --max-time 90 \
    "https://raw.githubusercontent.com/$source_repo/$source_commit/$patch_path/$name" \
    -o "$tmp/$name"
  actual=$(git hash-object "$tmp/$name")
  test "$actual" = "$blob_sha" || {
    echo "PINCTRL_PATCH_GIT_BLOB_SHA_MISMATCH: $name" >&2
    exit 43
  }
  if git -C "$tree" apply --check "$tmp/$name"; then
    git -C "$tree" apply "$tmp/$name"
  elif [[ "$name" = 0524-pinctrl-mediatek-size-sparse-eint-instances.patch ]]; then
    # Linux 6.18.63 shifted the EINT pin counting loop; port exactly the same
    # max(index)+1 sizing semantics rather than relaxing patch validation.
    python3 - "$tree/drivers/pinctrl/mediatek/mtk-eint.c" <<'PY'
from pathlib import Path
import sys
path=Path(sys.argv[1])
s=path.read_text()
old="\t\t\teint->base_pin_num[inst]++;"
new=("\t\t\teint->base_pin_num[inst] = max_t(u16,\n"
     "\t\t\t\teint->base_pin_num[inst], eint->pins[i].index + 1);")
assert s.count(old)==1, "PINCTRL_0524_REBASE_ANCHOR_MISMATCH"
s=s.replace(old,new,1)
assert s.count(new)==1, "PINCTRL_0524_REBASE_POSTCHECK_FAIL"
path.write_text(s)
print("T6_MT69XX_0524_EXACT_6_18_63_REBASE_PASS")
PY
  else
    echo "PINCTRL_SOURCE_PATCH_NOT_APPLICABLE: $name" >&2
    exit 44
  fi
  printf 'T6_MT69XX_UPSTREAM_PATCH_PASS name=%s blob=%s\n' "$name" "$blob_sha"
done <<'PINS'
0521-pinctrl-mediatek-add-mt69xx-provider.patch 4a783d277853742108d16821d834e4c72640f881
0522-pinctrl-mediatek-support-external-eint-provider.patch b48e01984b497eda09a9ef221e6319d93ba1162e
0523-pinctrl-mediatek-add-mt6990-sdk-eint-map.patch 0709bdbb70beceda9be8e417cc5994f0a42f0eaa
0524-pinctrl-mediatek-size-sparse-eint-instances.patch f978469e5b7edc1557c735d4a42a8a3afc8d0039
PINS
test -s "$tree/drivers/pinctrl/mediatek/pinctrl-mt69xx.c"
test -s "$tree/drivers/pinctrl/mediatek/pinctrl-mtk-mt69xx.h"
grep -Fq 'config PINCTRL_MT69XX' "$tree/drivers/pinctrl/mediatek/Kconfig"
grep -Fq 'mediatek,mt69xx-pinctrl' "$tree/drivers/pinctrl/mediatek/pinctrl-mt69xx.c"
echo T6_MT69XX_PINCTRL_UPSTREAM_PORT_ALL_FOUR_PATCHES_PASS
