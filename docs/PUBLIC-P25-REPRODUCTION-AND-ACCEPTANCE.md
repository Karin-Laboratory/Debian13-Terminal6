# Public Debian 13 Terminal 6 reproduction and acceptance

**State:** engineering candidate; C-unit LK boot and management network remain unverified.
This procedure contains **no signing, boot-slot changes or writes to hardware**.

## Public-source unsigned P25 build

On a disposable **native ARM64 Linux build host** (for example, an arm64
Ubuntu 24.04 VM), install prerequisites:

```sh
sudo apt-get update
sudo apt-get install -y git make gcc g++ python3 curl bc bison flex \
  libssl-dev libelf-dev device-tree-compiler cpio busybox-static
```

From a clean checkout that includes PR #14:

```sh
bash scripts/reproduce-public-unsigned-p25.sh /absolute/path/new-p25-work
```

The orchestrator downloads SHA-locked **public OSS sources**, compiles the
Air6-research DTB and official Linux 6.18.63 with MT6990 clock, MMC,
NETSYS/PHY/PCS and DSA support, embeds the P44 initramfs, constructs
`unsigned-p25/p25-unsigned.img` (exactly 33,554,432 bytes), and performs
an independent full boot-v2 header/gzip/DT-table/SHA readback.

Expected outputs:

- `new-p25-work/unsigned-p25/p25-unsigned.img`
- `new-p25-work/unsigned-p25/p25-receipt.json`
- `new-p25-work/linux-6.18.63/output/kernel.config`
- `new-p25-work/linux-6.18.63/output/public-mt6990-kernel-inputs.json`
- `new-p25-work/public-mt6990/source-receipt.json`
- `new-p25-work/dtb/board/terminal6-debian-ethernet-experimental.dtb`

This validates manufacturing structure, **not physical boot compatibility**.
Input identity is pinned; compiler/OS packages are not guaranteed bit-for-bit
identical between independently provisioned build VMs.

## Public Debian 13 arm64 P44 rootfs

On a disposable ARM64 Debian/Ubuntu system with `debootstrap`,
`debian-archive-keyring`, OpenSSH client and `systemctl`:

```sh
sudo bash scripts/build-public-p44-rootfs.sh \
  /absolute/path/new-p44-rootfs \
  /absolute/path/operator-ssh-authorized-keys
```

The second path is optional but **required for SSH key login** unless
authorized_keys is provisioned separately. It may contain only public keys.
No default root password or common device SSH host private key is provisioned.
Each booted device generates its own host keys. `lan2` uses DHCP through
systemd-networkd; the public management helper uses standard netlink,
not private `test23`/`test24` kernel modules.

Outputs: `debian13-p44-rootfs.tar.gz`,
`debian-package-manifest.txt`, `SHA256SUMS` and `STATUS.txt`. The
rootfs script **does not write eMMC or format P44**. Install/extract it only
using a separately verified, owner-controlled offline preparation plan.
Do not replace the currently working C-unit P44 without a tested rollback.

## What would constitute physical acceptance?

Only after the experimental board DTS/clock/power/SerDes routing has been
reviewed against C-unit observations and an owner-controlled signing step
has completed, an operator may select a *separately backed-up* trial
partition. Preserve stock slot B, current P25, P26, P44 and the emergency
UART path; verify partition identity and full readback before any slot change.

On the booted Debian C-unit, run the read-only acceptance helper:

```sh
sh scripts/verify-public-p25-cunit-readonly.sh
```

It checks Linux release, `rootfs_data` ext4, `eth1`, `lan2`, carrier,
systemd-networkd, and SSH. Independently capture first-boot UART and
raspi4-to-C SSH connectivity. A pass of the local helper is **not** proof
of provenance or cold boot; both must be measured independently.

**Do not mark complete** on successful source replay, a size-correct
unsigned image, or a syntax-valid DTB alone. Final hardware acceptance
requires LK handoff, P44 switch_root, management Ethernet/SSH, UART and
power-cycle persistence. Private signing keys and per-device calibration
must not be published.
