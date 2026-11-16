#!/usr/bin/env bash
# Pinned OpenWrt libubox/libubus/ubusd native Debian 13 AArch64 builder.
# Stage-only: no system install, device access or host network changes.
set -euo pipefail

readonly LIBUBOX_REV=a396f38a8568a1d670c240465cd8d24fdfdf6463
readonly UBUS_REV=db20eff5535fe3126c05dc0edc029caf0e82fe10
readonly LIBUBOX_REPO=https://github.com/openwrt/libubox.git
readonly UBUS_REPO=https://github.com/openwrt/ubus.git

usage() { echo "usage: $0 NEW_PRIVATE_STAGE_DIRECTORY" >&2; exit 2; }
[[ $# -eq 1 && -n "$1" ]] || usage
for tool in git cmake ninja gcc pkg-config readelf python3 sha256sum realpath; do
    command -v "$tool" >/dev/null || { echo "BLOCKED missing=$tool" >&2; exit 2; }
done
[[ "$(dpkg --print-architecture)" == arm64 ]] || {
    echo "BLOCKED must run under Debian13 arm64" >&2; exit 2;
}
source /etc/os-release
[[ "$ID" == debian && "$VERSION_ID" == 13 ]] || {
    echo "BLOCKED Debian 13 required" >&2; exit 2;
}
[[ "$1" == /* ]] || { echo "BLOCKED absolute output path required" >&2; exit 2; }
out="${1%/}"
[[ ! -e "$out" && ! -L "$out" && "$out" != "/" ]] || {
    echo "BLOCKED choose a new non-symlink stage" >&2; exit 2;
}
umask 077
mkdir -m 0700 -p "$out"
out="$(realpath "$out")"
work="$(mktemp -d)"
sock_pid=
cleanup() {
    if [[ -n "${sock_pid:-}" ]]; then
        kill "$sock_pid" 2>/dev/null || :
        wait "$sock_pid" 2>/dev/null || :
    fi
    rm -rf -- "$work"
}
trap cleanup EXIT INT TERM
prefix="$out/install"
mkdir -p "$prefix"

fetch_exact() {
    local url="$1" rev="$2" name="$3"
    git clone --quiet --no-checkout "$url" "$work/$name"
    git -C "$work/$name" checkout --quiet --detach "$rev"
    [[ "$(git -C "$work/$name" rev-parse HEAD)" == "$rev" ]] || {
        echo "BLOCKED pinned upstream revision mismatch" >&2; exit 2;
    }
}
fetch_exact "$LIBUBOX_REPO" "$LIBUBOX_REV" libubox
cmake -S "$work/libubox" -B "$work/ubox-build" -G Ninja \
    -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX="$prefix" \
    -DCMAKE_INSTALL_RPATH='$ORIGIN/../lib' \
    -DBUILD_LUA=OFF -DBUILD_EXAMPLES=OFF -DUNIT_TESTING=OFF
cmake --build "$work/ubox-build" --parallel 2
cmake --install "$work/ubox-build"

fetch_exact "$UBUS_REPO" "$UBUS_REV" ubus
cmake -S "$work/ubus" -B "$work/ubus-build" -G Ninja \
    -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX="$prefix" \
    -DCMAKE_PREFIX_PATH="$prefix" -DCMAKE_INCLUDE_PATH="$prefix/include" \
    -DCMAKE_LIBRARY_PATH="$prefix/lib" \
    -DCMAKE_BUILD_RPATH="$prefix/lib" \
    -DCMAKE_INSTALL_RPATH='$ORIGIN/../lib' \
    -DBUILD_LUA=OFF -DBUILD_EXAMPLES=OFF -DUNIT_TESTING=OFF
cmake --build "$work/ubus-build" --parallel 2
cmake --install "$work/ubus-build"

# Verify actual ABI of the outputs, not just their filenames.
for binary in "$prefix"/lib/libubox.so "$prefix"/lib/libubus.so \
              "$prefix"/lib/libblobmsg_json.so "$prefix"/sbin/ubusd \
              "$prefix"/bin/ubus; do
    [[ -e "$binary" ]] || { echo "FAIL missing staged runtime: $(basename "$binary")" >&2; exit 1; }
    readelf -h "$binary" | grep -Eq 'Machine: *AArch64' || {
        echo "FAIL ELF architecture mismatch: $(basename "$binary")" >&2; exit 1;
    }
done

# Real local socket IPC between newly built daemon + CLI. No synthetic PASS.
mkdir -p "$work/ipc"
LD_LIBRARY_PATH="$prefix/lib" "$prefix/sbin/ubusd" -s "$work/ipc/ubus.sock" \
    >"$work/ubusd.private.log" 2>&1 &
sock_pid=$!
ready=no
for _ in $(seq 1 30); do
    if [[ -S "$work/ipc/ubus.sock" ]] && \
       LD_LIBRARY_PATH="$prefix/lib" "$prefix/bin/ubus" \
           -s "$work/ipc/ubus.sock" list >/dev/null 2>&1; then
        ready=yes
        break
    fi
    kill -0 "$sock_pid" 2>/dev/null || break
    sleep 0.2
done
[[ "$ready" == yes ]] || { echo "FAIL real ubusd IPC did not establish" >&2; exit 1; }
kill "$sock_pid" 2>/dev/null || :
wait "$sock_pid" 2>/dev/null || :
sock_pid=

export CUNIT_STAGE="$prefix" CUNIT_OUT="$out" CUNIT_LIBUBOX_REV="$LIBUBOX_REV" CUNIT_UBUS_REV="$UBUS_REV"
python3 - <<'PY'
import hashlib, json, os, platform
from pathlib import Path
root = Path(os.environ["CUNIT_STAGE"])
files = {}
for rel in ("lib/libubox.so", "lib/libubus.so", "lib/libblobmsg_json.so",
            "sbin/ubusd", "bin/ubus"):
    files[rel] = hashlib.sha256((root / rel).read_bytes()).hexdigest()
manifest = {
    "os": "Debian 13", "arch": "arm64", "libc": platform.libc_ver()[0],
    "source_revisions": {
        "libubox": os.environ["CUNIT_LIBUBOX_REV"],
        "ubus": os.environ["CUNIT_UBUS_REV"],
    },
    "binary_sha256": files,
    "actual_ubusd_ubus_ipc": "PASS",
    "ambiorix_backend_loaded": False, "prplmesh_1905": "NOT_PROVEN",
}
(Path(os.environ["CUNIT_OUT"]) / "receipt.json").write_text(
    json.dumps(manifest, indent=2, sort_keys=True) + "\n")
PY
echo "DEBIAN13_ARM64_UBUS=PASS actual_ubusd_ipc=PASS amxrt=NOT_PROVEN ieee1905=NOT_PROVEN"
