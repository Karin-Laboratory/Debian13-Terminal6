#!/usr/bin/env python3
"""Volatile, isolated QEMU user-network host/guest TCP acceptance test.

Run as root on a C-unit Debian host. The guest image and all generated files
must reside in /run. No TAP or bridge is created; host IP forwarding,
physical interfaces, and P44 are unchanged. QEMU is stopped in a finally block.
"""

from __future__ import annotations

import os
import re
import select
import socket
import subprocess
import sys
import time
from pathlib import Path


RUN = Path("/run/cunit-kvm-host-guest-20261120-r9")
KERNEL = Path("/run/openwrt-armv8-initramfs-kernel.bin")
QEMU = "/usr/bin/qemu-system-aarch64"
HOST_PORT = 19222
GUESTFWD_PORT = 5555
GUEST_HTTP_PORT = 8080


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def main() -> int:
    require(os.geteuid() == 0, "run as root")
    require(KERNEL.is_file(), f"missing RAM-resident guest kernel: {KERNEL}")
    require(Path("/dev/kvm").exists(), "/dev/kvm unavailable")
    require(subprocess.run(["pgrep", "-af", "[q]emu-system-aarch64"],
                           capture_output=True).returncode != 0,
            "another QEMU process is active; refusing to overlap it")
    require(not Path("/sys/class/net/t6kvm0").exists(),
            "unexpected t6kvm0 exists; refusing to alter it")

    if RUN.exists():
        require(RUN.is_dir() and {p.name for p in RUN.iterdir()} == {"run.py"},
                f"{RUN} contains unexpected prior data; refusing to overwrite")
    else:
        RUN.mkdir(mode=0o700)
    echo_script = RUN / "guestfwd_echo.py"
    log_path = RUN / "serial.log"
    echo_script.write_text(
        "import sys\n"
        "r = sys.stdin.buffer\n"
        "while r.readline().strip(): pass\n"
        "body = b'host-reply-through-guestfwd\\n'\n"
        "sys.stdout.buffer.write(b'HTTP/1.0 200 OK\\r\\nContent-Length: ' + str(len(body)).encode() + b'\\r\\nConnection: close\\r\\n\\r\\n' + body)\n"
        "sys.stdout.buffer.flush()\n",
        encoding="ascii",
    )

    qemu_args = [
        QEMU, "-name", "cunit-isolated-host-guest-test",
        "-machine", "virt", "-cpu", "host", "-accel", "kvm",
        "-m", "256M", "-smp", "1", "-kernel", str(KERNEL),
        "-append", "console=ttyAMA0",
        "-display", "none", "-monitor", "none", "-serial", "stdio",
        "-no-reboot",
        "-netdev",
        f"user,id=net0,restrict=on,hostfwd=tcp:127.0.0.1:{HOST_PORT}-:{GUEST_HTTP_PORT},"
        f"guestfwd=tcp:10.0.2.4:{GUESTFWD_PORT}-cmd:/usr/bin/python3 {echo_script}",
        "-device", "virtio-net-device,netdev=net0",
    ]
    log = bytearray()
    proc: subprocess.Popen[bytes] | None = None

    def read_until(needle: bytes, timeout: float) -> bytes:
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            if proc is None or proc.stdout is None:
                raise RuntimeError("QEMU console is unavailable")
            ready, _, _ = select.select([proc.stdout], [], [], 0.2)
            if ready:
                chunk = os.read(proc.stdout.fileno(), 4096)
                if not chunk:
                    raise RuntimeError("QEMU serial console closed")
                log.extend(chunk)
                if needle in log:
                    return bytes(log)
            if proc.poll() is not None:
                raise RuntimeError(f"QEMU exited with status {proc.returncode}")
        raise TimeoutError(f"timed out waiting for {needle!r}")

    def wait_for_shell(timeout: float) -> bytes:
        end = time.monotonic() + timeout
        next_enter = time.monotonic()
        prompt = re.compile(rb"root@[^\r\n]*#")
        while time.monotonic() < end:
            if prompt.search(log):
                return bytes(log)
            if proc is None or proc.stdout is None:
                raise RuntimeError("QEMU console is unavailable")
            now = time.monotonic()
            if now >= next_enter and proc.stdin is not None:
                proc.stdin.write(b"\n")
                proc.stdin.flush()
                next_enter = now + 2.0
            ready, _, _ = select.select([proc.stdout], [], [], 0.2)
            if ready:
                chunk = os.read(proc.stdout.fileno(), 4096)
                if not chunk:
                    raise RuntimeError("QEMU serial console closed")
                log.extend(chunk)
            if proc.poll() is not None:
                raise RuntimeError(f"QEMU exited with status {proc.returncode}")
        raise TimeoutError("timed out waiting for an OpenWrt root shell prompt")

    def command(cmd: str, timeout: float = 15.0) -> bytes:
        require(proc is not None and proc.stdin is not None, "QEMU stdin unavailable")
        marker = f"__CUNIT_DONE_{time.monotonic_ns()}__".encode()
        proc.stdin.write(cmd.encode() + b"; echo " + marker + b"\n")
        proc.stdin.flush()
        # Wait for the shell's standalone echo output, not the terminal's
        # earlier echo of the submitted command line containing the marker.
        return read_until(b"\r\n" + marker + b"\r\n", timeout)

    try:
        proc = subprocess.Popen(qemu_args, stdin=subprocess.PIPE,
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                bufsize=0, start_new_session=True)
        read_until(b"Please press Enter to activate this console.", 90)
        wait_for_shell(60)

        net = command("ip link set eth0 nomaster 2>/dev/null || true; ip addr flush dev eth0; ip link set eth0 up; udhcpc -n -q -t 5 -i eth0; ip route replace default via 10.0.2.2 dev eth0; ip -4 addr show dev eth0; ip route", 20)
        require(b"10.0.2." in net and b"default via 10.0.2.2" in net,
                "guest did not obtain expected isolated user-network DHCP lease/default route")
        gw = command("ping -c 2 -W 2 10.0.2.2", 10)
        require(re.search(rb"2 packets transmitted, 2 packets received", gw) is not None,
                "guest could not ping QEMU user-network gateway")

        # Guest-initiated TCP through guestfwd reaches only this QEMU child
        # process; the response is generated locally and never routed onward.
        response = command(f"wget -T 8 -qO- http://10.0.2.4:{GUESTFWD_PORT}/", 12)
        require(b"host-reply-through-guestfwd" in response,
                "guestfwd host response was not received in the guest")

        # Start a temporary guest service entirely in the initramfs RAM.
        # Hostfwd is bound to loopback only; no host LAN listener is exposed.
        server = command(
            "if [ -x /usr/sbin/dropbear ]; then /usr/sbin/dropbear -R -E -p 8080 >/tmp/cunit-server.log 2>&1 & SERVER_KIND=dropbear; "
            "elif [ -x /usr/sbin/uhttpd ]; then mkdir -p /tmp/cunit-www; printf 'guest-reply-through-hostfwd\\n' > /tmp/cunit-www/index.html; /usr/sbin/uhttpd -f -h /tmp/cunit-www -p 0.0.0.0:8080 >/tmp/cunit-server.log 2>&1 & SERVER_KIND=http; "
            "else SERVER_KIND=none; fi; echo __CUNIT_SERVER_${SERVER_KIND}__; sleep 1; cat /tmp/cunit-server.log 2>/dev/null || true",
            8,
        )
        require(b"__CUNIT_SERVER_dropbear__" in server or b"__CUNIT_SERVER_http__" in server,
                "guest has no available temporary TCP service (dropbear/uhttpd)")
        with socket.create_connection(("127.0.0.1", HOST_PORT), timeout=5) as conn:
            conn.settimeout(5)
            banner = conn.recv(256)
            if b"SSH-2.0-" in banner:
                conn.sendall(b"SSH-2.0-cunit-isolated-probe\r\n")
                response = conn.recv(512)
                require(bool(response), "guest did not respond to host SSH identification")
                host_to_guest_result = "SSH protocol banner/identification exchange PASS"
            else:
                conn.sendall(b"GET / HTTP/1.0\r\nHost: cunit-guest\r\n\r\n")
                response = bytearray(banner)
                while True:
                    try:
                        chunk = conn.recv(1024)
                    except ConnectionResetError:
                        break
                    if not chunk:
                        break
                    response.extend(chunk)
                require(b"guest-reply-through-hostfwd" in response,
                        f"hostfwd did not return guest HTTP response: {bytes(response)!r}")
                host_to_guest_result = "HTTP request/response PASS"

        print("QEMU_KVM=PASS")
        print("GUEST_DHCP_AND_GATEWAY_PING=PASS")
        print("GUEST_TO_HOST_TCP_GUESTFWD=PASS")
        print("HOST_TO_GUEST_TCP_LOOPBACK_HOSTFWD=PASS")
        print("PHYSICAL_LAN_FORWARDING=NOT_TESTED (QEMU user networking, restrict=on)")
        print("HOST_TO_GUEST_PROTOCOL=" + host_to_guest_result)
        print(f"SERIAL_LOG={log_path}")
        return 0
    finally:
        if proc is not None and proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=8)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=3)
        log_path.write_bytes(log)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        raise
