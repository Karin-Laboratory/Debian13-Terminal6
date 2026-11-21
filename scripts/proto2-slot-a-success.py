#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""C-unit proto2: mark slot A successful ONLY after full Debian acceptance.

Disabled by default. A separate owner authorization must arm this service.
The known C-unit misc layout is guarded; unknown units/layouts fail closed.
No slot-B state, partition table, LK or P26 is modified.
"""
import argparse
import fcntl
import hashlib
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import time

KERNEL = "6.18.63-debian-t6-proto2"
P25_SHA256 = "74c1c98b31cdba54f71d16f1983fbeff347bb334c5ae7d7f1353cd57f734936e"
MISC_BYTES = 524288
CTRL_OFFSET = 2052
SECTOR_OFFSET = 2048
SECTOR_BYTES = 512
AUTHORIZE = Path("/etc/terminal6/authorize-slot-a-success")
AUTH_TEXT = "ALLOW_CUNIT_PROTO2_SLOT_A_SUCCESS_V1\n"
EVIDENCE_DIR = Path("/var/lib/terminal6/slot-a-success")
ERROR_PATTERNS = (
    r"EXT4-fs error",
    r"Buffer I/O error",
    r"blk_update_request: I/O error",
    r"mmc[0-9].*(?:timeout|error)",
    r"DATA TIMEOUT ERR",
    r"CQE recovery",
)


def command(*args):
    return subprocess.run(args, check=True, capture_output=True, text=True).stdout


def require(condition, reason):
    if not condition:
        raise RuntimeError(reason)


def part(name):
    matches = []
    for event in Path("/sys/class/block").glob("*/uevent"):
        pairs = dict(line.split("=", 1) for line in event.read_text().splitlines() if "=" in line)
        if pairs.get("PARTNAME") == name:
            device = Path("/dev") / pairs["DEVNAME"]
            require(device.is_block_device(), "INVALID_PART_" + name)
            matches.append(device)
    require(len(matches) == 1, "PART_COUNT_" + name)
    return matches[0]


def hash_device(path):
    digest = hashlib.sha256()
    with path.open("rb", buffering=0) as stream:
        while data := stream.read(1024 * 1024):
            digest.update(data)
    return digest.hexdigest()


def verify_debian_runtime():
    require(os.geteuid() == 0, "NOT_ROOT")
    require(Path("/proc/1/comm").read_text().strip() == "systemd", "NOT_SYSTEMD")
    require(re.search(r"(^|\s)bootslot=a(\s|$)", Path("/proc/cmdline").read_text()), "NOT_SLOT_A")
    require(os.uname().release == KERNEL, "WRONG_KERNEL")
    release = Path("/etc/os-release").read_text()
    require(re.search(r"(?m)^ID=debian$", release), "NOT_DEBIAN")
    require(re.search(r"(?m)^VERSION_ID=['\"]?13['\"]?$", release), "NOT_DEBIAN13")
    root = part("rootfs_data")
    root_info = command("findmnt", "-n", "-o", "SOURCE,FSTYPE,OPTIONS", "/").split()
    require(len(root_info) >= 3 and os.path.realpath(root_info[0]) == os.path.realpath(root), "ROOT_NOT_P44")
    require(root_info[1] == "ext4" and "rw" in root_info[2].split(","), "P44_NOT_RW")
    for file in ("/var/lib/terminal6/firstboot-complete", "/etc/ssh/ssh_host_ed25519_key"):
        require(Path(file).is_file() and Path(file).stat().st_size > 0, "SSH_PROVISION_NOT_COMPLETE")
    require(Path("/root/.ssh/authorized_keys").is_file() and
            Path("/root/.ssh/authorized_keys").stat().st_size > 0, "NO_OWNER_SSH_KEY")
    command("systemctl", "is-active", "--quiet", "ssh.service")
    command("systemctl", "is-active", "--quiet", "terminal6-proto2-wifi.service")
    require("inet " in command("ip", "-o", "-4", "addr", "show", "dev", "lan2"), "LAN2_NO_IPV4")
    require(any(Path("/sys/class/ieee80211").glob("phy*")), "WIFI_PHY_MISSING")
    kernel_log = command("journalctl", "-k", "-b", "--no-pager", "-o", "cat")
    require("merged 46 OTP calibration-free bytes" in kernel_log,
            "CURRENT_BOOT_OTP_ACK_MISSING")
    require("uploaded all 8 EEPROM buffer pages" in kernel_log,
            "CURRENT_BOOT_EEPROM_ACK_MISSING")
    for pattern in ERROR_PATTERNS:
        require(re.search(pattern, kernel_log, re.IGNORECASE) is None,
                "CURRENT_BOOT_STORAGE_ERROR")
    boot_a = part("boot_a")
    require(hash_device(boot_a) == P25_SHA256, "UNEXPECTED_BOOT_A_SHA")
    # Partition selection must refer to the same physical eMMC.
    misc = part("misc")
    boot_parent = re.sub(r"p\d+$", "", boot_a.name)
    misc_parent = re.sub(r"p\d+$", "", misc.name)
    require(boot_parent == misc_parent and boot_parent.startswith("mmcblk"),
            "MISC_BOOT_A_DEVICE_MISMATCH")
    return misc


def patch_misc(original):
    """Pure byte-level transformation, tested on synthetic C-unit snapshots."""
    require(len(original) == MISC_BYTES, "UNEXPECTED_MISC_SIZE")
    a = original[CTRL_OFFSET:CTRL_OFFSET + 5]
    b = original[CTRL_OFFSET + 5:CTRL_OFFSET + 10]
    require(a[0] == 0x0f and b == bytes((0x0e, 0x00, 0x01, 0x00, 0x00)),
            "UNKNOWN_AB_LAYOUT_OR_B_NOT_SAFE")
    require(a[3:] == b"\x00\x00", "UNKNOWN_A_UPTYPE_OR_PADDING")
    if a[1:3] == b"\x00\x01":
        return original, False
    require(1 <= a[1] <= 15 and a[2] == 0, "A_NOT_FINITE_SUCCESS_ZERO")
    result = bytearray(original)
    result[CTRL_OFFSET + 1] = 0  # A retry=0
    result[CTRL_OFFSET + 2] = 1  # A success=1
    require(result[CTRL_OFFSET + 5:CTRL_OFFSET + 10] == b, "B_MODIFIED")
    return bytes(result), True


def write_misc(misc, original, result):
    # Preserve a full, byte-exact misc backup BEFORE touching the one 512B
    # sector containing the A/B fields. No arbitrary userland "bootctl -s".
    EVIDENCE_DIR.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(EVIDENCE_DIR, 0o700)
    stamp = str(time.time_ns())
    backup = EVIDENCE_DIR / ("misc-before-" + stamp + ".img")
    fd = os.open(backup, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        require(os.write(fd, original) == len(original), "BACKUP_SHORT_WRITE")
        os.fsync(fd)
    finally:
        os.close(fd)
    require(backup.read_bytes() == original, "BACKUP_READBACK_FAIL")
    dir_fd = os.open(EVIDENCE_DIR, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(dir_fd)
    finally:
        os.close(dir_fd)
    fd = os.open(misc, os.O_RDWR | os.O_SYNC | os.O_CLOEXEC)
    try:
        require(stat.S_ISBLK(os.fstat(fd).st_mode), "MISC_NOT_BLOCK")
        current = os.pread(fd, MISC_BYTES, 0)
        require(current == original, "MISC_CHANGED_BEFORE_WRITE")
        sector = result[SECTOR_OFFSET:SECTOR_OFFSET + SECTOR_BYTES]
        require(len(sector) == SECTOR_BYTES, "INVALID_SECTOR")
        require(os.pwrite(fd, sector, SECTOR_OFFSET) == SECTOR_BYTES,
                "MISC_SHORT_WRITE")
        os.fsync(fd)
        verified = os.pread(fd, MISC_BYTES, 0)
        require(verified == result, "MISC_VERIFY_FAIL")
    finally:
        os.close(fd)
    print("SLOT_A_SUCCESS_WRITE_AND_FULL_MISC_READBACK_PASS")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--commit", action="store_true",
                        help="requires explicit owner authorization marker; otherwise check only")
    args = parser.parse_args()
    misc = verify_debian_runtime()
    lock_path = Path("/run/terminal6-slot-a-success.lock")
    with lock_path.open("w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        original = misc.read_bytes()
        result, changed = patch_misc(original)
        print("CURRENT_MISC_SHA256=" + hashlib.sha256(original).hexdigest())
        if not changed:
            print("SLOT_A_ALREADY_SUCCESS_B_PRESERVED")
            return
        if not args.commit:
            print("SLOT_A_SUCCESS_READY_DRY_RUN_ONLY")
            return
        require(AUTHORIZE.is_file() and not AUTHORIZE.is_symlink(), "OWNER_AUTH_REQUIRED")
        require(AUTHORIZE.stat().st_uid == 0 and stat.S_IMODE(AUTHORIZE.stat().st_mode) == 0o600,
                "UNSAFE_OWNER_AUTH_FILE")
        require(AUTHORIZE.read_text() == AUTH_TEXT, "OWNER_AUTH_CONTENT_MISMATCH")
        write_misc(misc, original, result)


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, OSError, subprocess.CalledProcessError) as exc:
        print("SLOT_A_SUCCESS_BLOCKED: " + str(exc), file=sys.stderr)
        sys.exit(1)
