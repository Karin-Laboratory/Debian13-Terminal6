#!/usr/bin/env bash
# SPDX-License-Identifier: MIT
# Assemble a buildable but still UNVALIDATED eMMC-enabled Air Terminal 6 DTB
# from independent board observations and pinned public MT6990 SoC source.
set -euo pipefail
[[ $# -eq 1 && "$1" = /* ]] || { echo "usage: stage-experimental-dtb.sh /absolute/output-dir" >&2; exit 2; }
out="$1"
[[ ! -e "$out" ]] || { echo "output must not exist" >&2; exit 2; }
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
for tool in git curl python3 cpp dtc; do command -v "$tool" >/dev/null; done
mkdir -p "$out/board" "$out/include/dt-bindings/interrupt-controller" "$out/include/dt-bindings/gpio" "$out/include/dt-bindings/power" "$out/include/dt-bindings/clock"
donor=https://raw.githubusercontent.com/13179415360/openwrt-mt6990-lg6851f/a40df9a5afb46716dea799acea69f17480df4d82
src=https://raw.githubusercontent.com/Karin-Laboratory/openwrt-terminal-6/d72aa96d60997c35bd127649527cc53ba1f3a89e
download() {
  local url="$1" dest="$2" blob="$3"
  curl -fsSL --retry 3 --max-time 90 "$url" -o "$dest"
  test "$(git hash-object "$dest")" = "$blob" || { echo "Pinned source mismatch: $dest" >&2; exit 1; }
}
download "$src/board/mt6990-air-terminal-6.dts" "$out/board/board-original.dts" 541b9b5380882409b2a11741ee0ed06a68e727ad
download "$donor/target/linux/mediatek/patches-6.18/969-arm64-dts-mediatek-add-mt6990-soc.patch" "$out/mt6990.patch" 4f24ec8183c5495a312ec5f1109164d7b770a770
download "$donor/target/linux/mediatek/files-6.18/include/dt-bindings/power/mt6990-power.h" "$out/include/dt-bindings/power/mt6990-power.h" c221b322fb437683d052ec4241a33afaecb33979
download "$donor/target/linux/mediatek/files-6.18/include/dt-bindings/clock/mt6990-clk.h" "$out/include/dt-bindings/clock/mt6990-clk.h" eea7fbe58a5d5b7357c5ddb83eff6ffb74b3801a
for pair in \
  "interrupt-controller/arm-gic.h:887f53363e8a633ba85c8a459313c37b71a729a5" \
  "interrupt-controller/irq.h:9e3d183e138191fe5227cb5ffc5ff52d81036b15" \
  "gpio/gpio.h:b5d531237448241f1870e7d8d4cf1a6411877562"; do
  name="${pair%%:*}" blob="${pair#*:}"
  download "https://raw.githubusercontent.com/torvalds/linux/v6.18/include/dt-bindings/$name" "$out/include/dt-bindings/$name" "$blob"
done
python3 "$root/scripts/prepare-experimental-dts.py" "$out/mt6990.patch" "$out/board/board-original.dts" "$out/board/mt6990.dtsi" "$out/board/terminal6-debian-experimental.dts"
cpp -nostdinc -undef -D__DTS__ -x assembler-with-cpp \
  -I "$out/include" -I "$out/board" \
  "$out/board/terminal6-debian-experimental.dts" "$out/board/preprocessed.dts"
dtc -I dts -O dtb -o "$out/board/terminal6-debian-experimental.dtb" "$out/board/preprocessed.dts"
dtc -I dtb -O dts -o "$out/board/roundtrip.dts" "$out/board/terminal6-debian-experimental.dtb"
grep -q 'softbank,air-terminal-6' "$out/board/roundtrip.dts"
echo "EXPERIMENTAL_DTB_COMPILED_NOT_BOOT_VALIDATED"
sha256sum "$out/board/terminal6-debian-experimental.dtb"
