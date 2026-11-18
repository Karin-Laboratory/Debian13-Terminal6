#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Nonpersistent ESP32 UART1 AT/version probe. No RF or firmware operations."""
from __future__ import annotations

import argparse
import fcntl
import os
import select
import termios
import time
import tty


def exchange(fd: int, command: bytes, timeout: float) -> bytes:
    os.write(fd, command + b"\r\n")
    deadline = time.monotonic() + timeout
    response = bytearray()
    while time.monotonic() < deadline and len(response) < 1024:
        ready, _, _ = select.select([fd], [], [], max(0, deadline - time.monotonic()))
        if not ready:
            break
        try:
            response.extend(os.read(fd, 1024 - len(response)))
        except BlockingIOError:
            pass
        if b"\r\nOK\r\n" in response or b"\r\nERROR\r\n" in response:
            break
    return bytes(response)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--device", default="/dev/ttyS1")
    parser.add_argument("--timeout", type=float, default=2.0)
    args = parser.parse_args()
    if args.device != "/dev/ttyS1" or not 0.2 <= args.timeout <= 5.0:
        parser.error("only ttyS1 and a 0.2-5.0 second timeout are allowed")
    fd = os.open(args.device, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
    try:
        fcntl.ioctl(fd, termios.TIOCEXCL)
        saved = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            attrs = termios.tcgetattr(fd)
            attrs[2] &= ~termios.CRTSCTS
            attrs[4] = attrs[5] = termios.B115200
            termios.tcsetattr(fd, termios.TCSANOW, attrs)
            response = exchange(fd, b"AT", args.timeout)
            if b"\r\nOK\r\n" not in response:
                print("ESP32_AT_RESPONSE=NOT_OBSERVED")
                return 2
            print("ESP32_AT_RESPONSE=PASS")
            version = exchange(fd, b"AT+GMR", args.timeout)
            if b"\r\nOK\r\n" not in version:
                print("ESP32_VERSION=NOT_OBSERVED")
                return 0
            for line in version.decode("ascii", errors="ignore").splitlines():
                if line.lower().startswith(("at version:", "sdk version:", "compile time:")):
                    print(line[:100])
            print("ESP32_VERSION_RESPONSE=PASS")
            return 0
        finally:
            termios.tcsetattr(fd, termios.TCSANOW, saved)
    finally:
        os.close(fd)


if __name__ == "__main__":
    raise SystemExit(main())
