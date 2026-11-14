# hostapd 2.12 ARM64候補ビルド記録

- Source: hostapd 2.12 upstream release archive.
- Source archive SHA-256: `f43502561c28ba47ab77e18e1a973d07361c68cc8b14178e619bd5796b70eabd`.
- Build target: Debian arm64 / `nl80211` backend; IEEE 802.11ax/be, SAE enabled.
- Output SHA-256 (owner-private temporary artifact; not committed): `b55f53e683ccb3f639a7922dead3d9c67553e77d35369400944ba1e0cf2b3aab`.
- ELF: AArch64, PIE, dynamic loader `/lib/ld-linux-aarch64.so.1`; dependencies include libnl, OpenSSL, glibc.
- Runtime check: `qemu-aarch64 -L /usr/aarch64-linux-gnu -E LD_LIBRARY_PATH=<temporary-arm64-sysroot> hostapd -v` printed `hostapd v2.12`.

This is a host-side candidate build only. It was not installed on the C-unit, and the version output does not test `nl80211`, AP startup, 6GHz operation, EHT negotiation, MLO, or packet transfer. The temporary source tree, binary, sysroot, and package archives are excluded from Git. Do not treat this candidate as approved firmware or a device-ready package before target library/kernel ABI and runtime testing.
