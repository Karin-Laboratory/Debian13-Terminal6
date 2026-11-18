#!/usr/bin/env bash
# Build official Ambiorix UBus backend against Debian13 AArch64 OpenWrt UBus.
# Only on an isolated Debian13 arm64 VM. No system install or RF/device changes.
set -euo pipefail

readonly BACKEND_REV=c74118306cd9f4557de2a8963c21f6d4a94c6f89
usage() {
    echo "usage: $0 EXISTING_BACKEND_CHECKOUT PRIVATE_ARM64_AMX_PREFIX VERIFIED_UBUS_INSTALL NEW_PRIVATE_OUTPUT" >&2
    exit 2
}
[[ $# -eq 4 ]] || usage
for tool in git make gcc readelf python3 pkg-config realpath; do
    command -v "$tool" >/dev/null || { echo "BLOCKED missing=$tool" >&2; exit 2; }
done
source /etc/os-release
[[ "$ID" == debian && "$VERSION_ID" == 13 &&
   "$(dpkg --print-architecture)" == arm64 ]] || {
    echo "BLOCKED native Debian 13 AArch64 required" >&2; exit 2;
}
for path in "$1" "$2" "$3" "$4"; do
    [[ "$path" == /* ]] || { echo "BLOCKED absolute paths required" >&2; exit 2; }
done
src=$(realpath "$1")
amx=$(realpath "$2")
ubus=$(realpath "$3")
out="${4%/}"
[[ -d "$src" && -d "$amx" && -d "$ubus" && ! -e "$out" && ! -L "$out" ]] || {
    echo "BLOCKED source/prefix missing or output exists" >&2; exit 2;
}
[[ "$(git -C "$src" rev-parse HEAD)" == "$BACKEND_REV" ]] || {
    echo "BLOCKED backend differs from Stage 5 pinned commit" >&2; exit 2;
}
for name in libamxc libamxp libamxd libamxb; do
    [[ -f "$amx/lib/$name.so" ]] || {
        echo "BLOCKED missing AArch64 Ambiorix core: $name" >&2; exit 2;
    }
    readelf -h "$amx/lib/$name.so" | grep -q 'Machine: *AArch64' || {
        echo "BLOCKED Ambiorix ELF Machine mismatch: $name" >&2; exit 2;
    }
done
for name in libubox libubus libblobmsg_json; do
    [[ -f "$ubus/lib/$name.so" ]] || {
        echo "BLOCKED native OpenWrt UBus runtime missing: $name" >&2; exit 2;
    }
    readelf -h "$ubus/lib/$name.so" | grep -q 'Machine: *AArch64' || {
        echo "BLOCKED UBus ELF Machine mismatch: $name" >&2; exit 2;
    }
done
[[ -x "$ubus/sbin/ubusd" ]] || { echo "BLOCKED native ubusd missing" >&2; exit 2; }
[[ -f "$ubus/include/libubus.h" && -d "$ubus/include/libubox" ]] || {
    echo "BLOCKED UBus development headers missing" >&2; exit 2;
}
umask 077
mkdir -m 0700 -p "$out"
out=$(realpath "$out")
work=$(mktemp -d)
trap 'rm -rf -- "$work"' EXIT
cp -a -- "$src"/. "$work/backend"
export PKG_CONFIG_PATH="$ubus/lib/pkgconfig:$amx/lib/pkgconfig"
export CFLAGS="-I$ubus/include -I$amx/include"
export CPPFLAGS="$CFLAGS"
export LDFLAGS="-L$ubus/lib -L$amx/lib -Wl,-rpath,$ubus/lib -Wl,-rpath,$amx/lib"
export LD_LIBRARY_PATH="$ubus/lib:$amx/lib"
# The official backend is built, not a reimplementation of AMX or IEEE 1905.
make -C "$work/backend" --jobs 2
module=$(find "$work/backend/output" -type f -name 'mod-amxb-ubus.so' -print -quit)
[[ -n "$module" && -s "$module" ]] || {
    echo "FAIL official make did not produce mod-amxb-ubus.so" >&2; exit 1;
}
readelf -h "$module" | grep -q 'Machine: *AArch64' || {
    echo "FAIL native backend ELF Machine mismatch" >&2; exit 1;
}
mkdir -p "$out/install/lib/amxb"
cp "$module" "$out/install/lib/amxb/mod-amxb-ubus.so"
for item in "$amx"/lib/libamx*.so* "$ubus"/lib/libub*.so* \
            "$ubus"/lib/libblobmsg_json.so* "$ubus"/lib/libjson_script.so*; do
    [[ -f "$item" ]] || continue
    cp -L -- "$item" "$out/install/lib/$(basename "$item")"
done
mkdir -p "$out/install/sbin" "$out/install/bin"
cp "$ubus/sbin/ubusd" "$out/install/sbin/ubusd"
cp "$ubus/bin/ubus" "$out/install/bin/ubus"
sha256sum "$out/install/lib/amxb/mod-amxb-ubus.so" | awk '{print $1}' > "$out/backend.sha256"
echo "AMXRT_UBUS_STAGE=BUILT_NATIVE_ARM64 runtime_backend_load=NOT_PROVEN ieee1905=NOT_PROVEN"
