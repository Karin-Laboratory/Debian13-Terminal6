# C-unit GNSS porting assessment

Date: 2026-11-14 JST  
Target: SoftBank Air Terminal 6 C-unit, Debian 13 arm64, Linux 6.18.63-debian-t6-proto2.

## A/C runtime comparison

### Stock A-unit, read-only

- Linux 5.4.238; `gps_drv` and `conninfra` modules loaded.
- Character devices `/dev/gps_emi`, `/dev/gpsdl0`, and `/dev/gpsdl1` present.
- `/usr/bin/gnss` and `/usr/bin/mtk_agpsd` running; `/etc/init.d/gnss` starts `gnss` when UCI enables it and optionally adds debug/AGPS flags.
- GNSS support data and libraries are present in the stock filesystem. They are device-vendor assets and are not copied or published here.
- A was not modified. No location or coordinates were collected.

### Debian C-unit, read-only

- Runtime has no GNSS character device, GNSS module, GNSS daemon, or GNSS userspace tooling.
- The live Device Tree does include enabled `mediatek,mt6990-gps` at `/gps@18C00000`, with named regions `conn_infra_base`, `conn_gps_base`, `conn_dyn_base`, `status_dummy_cr`, `tia2_gps_on`, and `tia2_gps_rc_sel`; a GPS reserved-memory phandle and interrupt resources are present.
- The C kernel config has no active GPS/GNSS config symbol. The existing 6.18 build source has no MT6990 GNSS driver.
- A matching GPL-2.0 driver source is publicly available in [mainline-mt6991, pinned commit](https://github.com/liudaoziwa/mainline-mt6991/tree/8e7a8e2f05ec3371bf6e498386c04b29bf03d404/drivers/misc/mediatek/connectivity/gps). Its v062 data-link driver lists `mediatek,mt6990-gps`, maps MT6990 to the SOC711X EMI layout, and consumes the named MMIO/IRQ resources found in the C-unit DT.

## Host build attempt

The public v062 module was copied to private workspace scratch and built against the current C-unit 6.18.63 kernel build tree. No binary was installed on either device.

1. Compilation first stopped because the Debian kernel's MediaTek SIP header lacks `MTK_SIP_KERNEL_GPS_CONTROL`.
2. A workspace-only compile experiment added the upstream call ID `MTK_SIP_SMC_CMD(0x537)`. The v062 driver sources then compiled and linked into the intermediate `gps_drv_dl_v062.o`.
3. Module post-processing failed because the target kernel has no matching conninfra exports. The unresolved interface includes `conninfra_get_emi_phy_addr`, `conninfra_pwr_off`, `conninfra_bus_clock_ctrl`, `conninfra_spi_read`, and other `conninfra_*`/metlog functions. Therefore no usable `.ko` was produced.

The 0x537 call ID is also present in the public [SBA6D-OSS MTK SIP header](https://github.com/soralis0912/SBA6D-OSS/blob/c7508cb46a6f51c9873604d6a94c94d5c433a8b6/buildroot/openwrt/target/linux/gem6xxx/files-5.4/include/linux/soc/mediatek/mtk_sip_svc.h). This confirms the software interface definition, but does not prove that the C-unit secure firmware accepts every GPS operation under Debian.

## Assessment and next implementation gate

The C DT and public v062 driver are structurally aligned, so this is a concrete driver-port candidate rather than a speculative DT node. The driver is not standalone: it relies on MediaTek conninfra power/clock/EMI/SPI services, GPS secure-monitor calls, firmware loading, and a compatible user-space stack.

Next:

1. Identify and build the **MT6990-specific** conninfra source/API for the 6.18 C kernel. Do not substitute MT6991 platform code without proving the hardware ABI.
2. Verify the complete module links against matching conninfra symbols and that the kernel/DT resource and IRQ counts agree.
3. Audit secure-firmware GPS SMC availability and the C-unit's own stock GNSS firmware/package interface. Keep proprietary GNSS payloads and location data private.
4. Only then stage a reversible module/service test with Ethernet, SSH and UART recovery verified. Capture device registration and receive-only GNSS evidence; do not enable AGPS network activity until that path is separately reviewed.

## Result

Status is **BLOCKED at matched conninfra/secure-firmware integration**. No GNSS hardware initialization, firmware upload, location acquisition, or C-unit persistent change was attempted. This result is distinct from hardware absence: DT resources exist, but function operation is unverified.

Related current overview: [C-unit feature porting ledger](CUNIT-FEATURE-PORTING-LEDGER-20261114.ja.md).
