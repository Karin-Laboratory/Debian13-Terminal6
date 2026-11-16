#!/bin/sh
set -eu

if [ "$#" -lt 4 ] || [ "$#" -gt 5 ]; then
    echo "usage: AMX_HOST_PREFIX=<host-tools-prefix> $0 <clean-prplMesh-6.0.1-checkout> <hostapd-layout-root> <target-AMX-prefix> <build-dir> [CMake-toolchain-file]" >&2
    exit 2
fi
src=$(realpath "$1")
hostapd_root=$(realpath "$2")
amx_prefix=$(realpath "$3")
build=$(realpath -m "$4")
toolchain_file=${5:-}
if [ -n "$toolchain_file" ]; then
    toolchain_file=$(realpath "$toolchain_file")
fi
host_amx_prefix=${AMX_HOST_PREFIX:-$amx_prefix}
host_amx_prefix=$(realpath "$host_amx_prefix")
target_sysroot=${CUNIT_TARGET_SYSROOT:-}
repo_root=$(realpath "$(dirname "$0")/../..")
patch_file="$repo_root/patches/prplmesh/0001-linux-bpl-configurable-radios-and-secure-security-modes.patch"
expected=5ba21ee04a3b34f0d99635eeacd547d78cb67efe
actual=$(git -C "$src" rev-parse HEAD)
if [ "$actual" != "$expected" ]; then
    echo "unexpected prplMesh revision: $actual" >&2
    exit 1
fi
all_status=$(git -C "$src" status --porcelain --untracked-files=all)
patch_status=$(git -C "$src" status --porcelain --untracked-files=all -- \
    CMakeLists.txt \
    framework/platform/bpl/cfg/linux/bpl_cfg_ifaces.cpp.in \
    framework/platform/bpl/cfg/linux/bpl_cfg_wifi.cpp)
if [ -n "$all_status" ] && [ "$all_status" != "$patch_status" ]; then
    echo "source checkout has unrelated changes; use a clean isolated worktree" >&2
    exit 1
fi
if git -C "$src" apply --reverse --unidiff-zero --check "$patch_file"; then
    : # patch is already present in this isolated build checkout
elif git -C "$src" apply --unidiff-zero --check "$patch_file"; then
    git -C "$src" apply --unidiff-zero "$patch_file"
else
    echo "cannot apply or verify already-applied prplMesh patch" >&2
    exit 1
fi

wpa_ctrl_header=$(find "$hostapd_root" -path '*/hostapd-*/src/common/wpa_ctrl.h' -print -quit)
if [ -z "$wpa_ctrl_header" ]; then
    echo "hostapd source tree (2.12) not found below hostapd-layout-root" >&2
    exit 1
fi
hostapd_include=${wpa_ctrl_header%/src/common/wpa_ctrl.h}
amx_config=$(find "$amx_prefix/lib" -name libamxc.so -print -quit)
if [ -z "$amx_config" ]; then
    echo "cannot locate Ambiorix library directory below AMX-prefix/lib" >&2
    exit 1
fi
amx_libdir=${amx_config%/*}
for lib in libamxc libamxp libamxd libamxb libamxs libamxo libamxj libamxrt; do
    if ! find "$amx_libdir" -maxdepth 1 -name "$lib.so*" -print -quit | grep -q .; then
        echo "missing Ambiorix dependency: $lib" >&2
        exit 1
    fi
done
if [ ! -x "$host_amx_prefix/bin/amxo-cg" ]; then
    echo "missing host-runnable amxo-cg from AMX_HOST_PREFIX" >&2
    exit 1
fi
host_amx_config=$(find "$host_amx_prefix/lib" -name libamxc.so -print -quit)
if [ -z "$host_amx_config" ]; then
    echo "cannot locate host Ambiorix libraries below AMX_HOST_PREFIX/lib" >&2
    exit 1
fi
host_amx_libdir=${host_amx_config%/*}
export PATH="$host_amx_prefix/bin:$PATH"
# CMake executes amxo-cg on the build host. Keep its loader path separate from
# target AArch64 libraries to avoid attempting to load target ELF objects.
export LD_LIBRARY_PATH="$host_amx_libdir${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"

cmake_prefix_path=$amx_prefix
cmake_include_path="$amx_prefix/include"
cmake_library_path=$amx_libdir
if [ -n "$toolchain_file" ]; then
    if [ -z "$target_sysroot" ] || [ ! -d "$target_sysroot/usr/include" ]; then
        echo "cross build requires CUNIT_TARGET_SYSROOT with target headers" >&2
        exit 1
    fi
    target_sysroot=$(realpath "$target_sysroot")
    target_pc="$target_sysroot/usr/lib/aarch64-linux-gnu/pkgconfig:$target_sysroot/usr/share/pkgconfig"
    export PKG_CONFIG_SYSROOT_DIR="$target_sysroot"
    export PKG_CONFIG_LIBDIR="$target_pc"
    export PKG_CONFIG_PATH="$target_pc"
    cmake_prefix_path="$amx_prefix;$target_sysroot/usr"
    cmake_include_path="$amx_prefix/include;$target_sysroot/usr/include"
    cmake_library_path="$amx_libdir;$target_sysroot/usr/lib/aarch64-linux-gnu;$target_sysroot/lib/aarch64-linux-gnu;$target_sysroot/usr/lib"
fi

set -- -S "$src" -B "$build" -G Ninja \
    -DTARGET_PLATFORM=linux \
    -DBWL_TYPE=NL80211 \
    -DBUILD_TESTS="${PRPLMESH_BUILD_TESTS:-ON}" \
    -DUSE_PRPLMESH_WHM=OFF \
    -DCMAKE_BUILD_TYPE=Release \
    -DCMAKE_INSTALL_PREFIX="$build/install" \
    -DCMAKE_PREFIX_PATH="$cmake_prefix_path" \
    -DCMAKE_INCLUDE_PATH="$cmake_include_path" \
    -DCMAKE_LIBRARY_PATH="$cmake_library_path" \
    -DCMAKE_BUILD_RPATH="$amx_libdir" \
    -DCMAKE_INSTALL_RPATH="\$ORIGIN/../lib;\$ORIGIN" \
    -DCMAKE_INSTALL_RPATH_USE_LINK_PATH=OFF \
    -DCMAKE_CXX_FLAGS="-Wno-ignored-attributes -Wno-overloaded-virtual -I$amx_prefix/include" \
    -DPLATFORM_BUILD_DIR="$hostapd_root" \
    -DHOSTAPD_INCLUDE_DIR="$hostapd_include" \
    -DAMXO_CG_EXECUTABLE="$host_amx_prefix/bin/amxo-cg"
if [ -n "$toolchain_file" ]; then
    set -- "$@" "-DCMAKE_TOOLCHAIN_FILE=$toolchain_file"
fi
cmake "$@"
mkdir -p "$build/stage"
DESTDIR="$build/stage" cmake --build "$build" --target install --parallel "${JOBS:-4}"
staged_prefix="$build/stage$build/install"
mkdir -p "$staged_prefix/lib"
for lib in libamxc libamxp libamxd libamxb libamxs libamxo libamxj libamxrt; do
    found=false
    for path in "$amx_libdir/$lib.so"*; do
        [ -e "$path" ] || continue
        cp -a "$path" "$staged_prefix/lib/"
        found=true
    done
    if [ "$found" != true ]; then
        echo "missing staged Ambiorix shared library: $lib" >&2
        exit 1
    fi
done
if [ "${PRPLMESH_BUILD_TESTS:-ON}" = ON ]; then
    ctest --test-dir "$build" --output-on-failure
else
    echo "CTest skipped because PRPLMESH_BUILD_TESTS=OFF"
fi
echo "PRPLMESH_STAGE=$build/stage"
