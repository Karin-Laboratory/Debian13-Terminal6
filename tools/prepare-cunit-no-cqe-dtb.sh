#!/usr/bin/env bash
# SPDX-License-Identifier: MIT
# Offline-only candidate. Does not sign, flash, or touch a device.
set -euo pipefail
export LC_ALL=C
umask 077

input=${1:?usage: prepare-cunit-no-cqe-dtb.sh INPUT_DTB NEW_PRIVATE_DIRECTORY}
outdir=${2:?usage: prepare-cunit-no-cqe-dtb.sh INPUT_DTB NEW_PRIVATE_DIRECTORY}
expected=f9f24ba152d6714626b6c79c205cf190b3875629ef60d73357c769d2d2ea10e3
node=/mmc@11230000

[[ -f $input && ! -L $input ]] || { echo 'input is not a regular file' >&2; exit 1; }
actual=$(sha256sum "$input" | cut -d' ' -f1)
[[ $actual == "$expected" ]] || { echo 'input DTB SHA mismatch' >&2; exit 1; }
for tool in fdtget fdtput dtc diff sed; do command -v "$tool" >/dev/null || exit 1; done
fdtget -p "$input" "$node" | grep -qx supports-cqe || { echo 'CQE property missing' >&2; exit 1; }
[[ ! -e $outdir && ! -L $outdir ]] || { echo 'output directory already exists' >&2; exit 1; }
mkdir -m 0700 -- "$outdir"
cp -- "$input" "$outdir/cqe-disabled.dtb"
chmod 0600 "$outdir/cqe-disabled.dtb"
dtc -I dtb -O dts -o "$outdir/before.dts" "$input" 2> "$outdir/dtc-before.stderr"
[[ $(grep -c 'supports-cqe;' "$outdir/before.dts") == 1 ]] || { echo 'unexpected CQE property count' >&2; exit 1; }
fdtput -d "$outdir/cqe-disabled.dtb" "$node" supports-cqe
if fdtget -p "$outdir/cqe-disabled.dtb" "$node" | grep -qx supports-cqe; then
    echo 'CQE property remains' >&2; exit 1
fi
dtc -I dtb -O dts -o "$outdir/after.dts" "$outdir/cqe-disabled.dtb" 2> "$outdir/dtc-after.stderr"
sed '/supports-cqe;/d' "$outdir/before.dts" > "$outdir/expected.dts"
diff -q "$outdir/expected.dts" "$outdir/after.dts" >/dev/null || {
    echo 'unexpected Device Tree difference' >&2; exit 1;
}
sha256sum "$input" "$outdir/cqe-disabled.dtb"
stat -c 'bytes=%s mode=%a file=%n' "$outdir/cqe-disabled.dtb"
echo 'DTB_CQE_PROPERTY_REMOVAL_ONLY=PASS'
