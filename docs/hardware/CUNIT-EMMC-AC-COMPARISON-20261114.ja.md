# A/C eMMC comparison and conservative CQE candidate

Date: 2026-11-14 JST. A was queried read-only. C storage, DT, kernel, and runtime configuration were not changed.

## Observations

| Field | A, stock 5.4.238 | C, Debian 13 / 6.18.63 |
|---|---|---|
| Controller and card mapping | 11230000.mmc → host mmc0, eMMC 4FTE4R, includes PARTNAME rootfs_b | 11230000.mmc → host mmc1, active root PARTNAME rootfs_data |
| Runtime mode | HS400, 8-bit, 1.8 V; debugfs requested 160 MHz, actual 94,999,965 Hz | HS400, 8-bit, 1.8 V; debugfs requested 200 MHz, actual 189,999,931 Hz |
| CMDQ | EXT_CSD CMDQ_SUPPORT=1, depth 16, CMDQ_MODE_EN=0; sysfs cmdq_en=1 | EXT_CSD support, depth 16; current sysfs cmdq_en=0; prior EXT_CSD read showed mode disabled |
| Wear indicators | LIFE_TIME A/B 0x01/0x01, PRE_EOL 0x01 | LIFE_TIME A/B 0x01/0x01, PRE_EOL 0x01 |
| Errors | No MMC error in the sampled log; no debugfs err_stats file | Current sampled counters all zero; historical data-timeout/CQE recovery followed by block WRITE and ext4 I/O errors |

The C failure log establishes an ordering: MSDC data timeout (dat_err=-110) → CQE recovery → block write I/O error → ext4 unwritten-extent and buffer I/O errors. It does not identify whether the initiating fault is controller/DMA, CQE, HS400 timing, power/clock, or media. The ext4 messages are downstream evidence of failed writes.

The A/C clock values are single runtime samples and differ. They are not a controlled frequency experiment. Matching eMMC model and normal wear indicators do not prove identical board conditions or exclude intermittent media faults. “Host Software Queue enabled” is not proof that card hardware CMDQ is enabled. A also reported EXT_CSD CMDQ_MODE_EN=0 while its runtime sysfs cmdq_en was 1; prefer the runtime attribute and do not infer active state from this EXT_CSD field.

## Source scope

The local C 6.18.63 source confirms that supports-cqe controls host CQE capability and CQHCI initialization; MMC core enables CMDQ only when both the card and host support it. Removing the boolean property is therefore the smallest host-side way to bypass CQE while retaining ordinary DMA.

The available upstream stable v5.4.238 sources are not the A vendor source. The A runtime and kernel image show vendor CQE additions/backports; the exact vendor mtk-sd.c, CQHCI and MMC core source was not available for a line-by-line comparison. No claim is made about the A vendor DMA descriptor, timeout, HS400 enhanced-strobe or recovery implementation relative to C. This comparison gap remains open.

## Candidate and test gate

Existing host-side candidate: delete supports-cqe from /mmc@11230000 only. The boolean must be absent; assigning numeric zero leaves a boolean property present. The change is not applied to C.

Existing host-side DT semantic validation passed. Hardware boot validation is NOT RUN. If a separately signed and recoverable test boot later becomes available, first confirm the live DT, host CQE capability off, runtime cmdq_en=0, and unchanged HS400/clock settings. Do not write-test P44. If the CQE-only candidate fails on a separate safe test medium, evaluate frequency reduction and HS400 disablement as independent candidates, one change per run.

## Safety and recovery status

The existing private C rootfs tar and supplemental volatile-state tar passed SHA256 and full tar-stream/list checks on their raspi4 backup host. This proves archive integrity, not a complete restore-and-boot. SSH routing and the C UART getty/device plus the raspi4 USB serial adapter were present; no UART reset or storage recovery operation was performed. P44 remains unsuitable for load testing until a separate safe test target and complete restore procedure are verified.

Private card identifiers, raw logs, backup contents and calibration data are excluded. See private operational archive locally.
