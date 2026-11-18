#!/usr/bin/env python3
"""Host-only external mesh recovery watcher using upstream wpa_cli commands.

A supervised auto-rejoin is *not* native wpa_supplicant recovery. This process
observes a network-interface DOWN->UP cycle in a disposable network namespace
and performs exactly one mesh_group_remove/mesh_group_add sequence. No radio
config, regulatory setting, kernel protocol or device is changed.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import re
import subprocess
import sys
import time


def interface_is_up(namespace: str, ifname: str) -> bool:
    proc = subprocess.run(
        ["ip", "-n", namespace, "-o", "link", "show", "dev", ifname],
        capture_output=True, text=True, timeout=3, check=True,
    )
    flags = re.search(r"<([^>]+)>", proc.stdout)
    if not flags:
        raise RuntimeError("could not parse IFF_UP for mesh peer")
    return "UP" in flags.group(1).split(",")


def group_rejoin(namespace: str, ctrl: str, ifname: str, network: int) -> bool:
    def command(*args: str) -> bool:
        proc = subprocess.run(
            ["ip", "netns", "exec", namespace, "wpa_cli",
             "-p", ctrl, "-i", ifname, *args],
            capture_output=True, text=True, timeout=8, check=False,
        )
        return proc.returncode == 0 and proc.stdout.strip() == "OK"

    return (command("mesh_group_remove", ifname) and
            command("mesh_group_add", str(network)))


def supervise(namespace: str, ifname: str, ctrl: str, network: int,
              ready: Path, receipt: Path, budget: float, interval: float) -> int:
    # Fail if called against a real namespace or radio. The test creates
    # cmesh-* namespaces only and never names a physical device.
    if not namespace.startswith("cmesh-") or ifname != "meshB":
        raise ValueError("watcher requires the owned cmesh-* meshB test peer")
    if ready.exists() or receipt.exists():
        raise ValueError("refusing stale marker/receipt")
    deadline = time.monotonic() + budget
    if not interface_is_up(namespace, ifname):
        raise ValueError("B must initially be UP before arming")
    ready.write_text("SUPERVISOR_READY=PASS\n", encoding="ascii")
    saw_down = False
    while time.monotonic() < deadline:
        up = interface_is_up(namespace, ifname)
        if not up:
            saw_down = True
        elif saw_down:
            # No passwords, MAC addresses or wpa logs in this receipt.
            ok = group_rejoin(namespace, ctrl, ifname, network)
            receipt.write_text(
                "SUPERVISOR_REJOIN=" + ("PASS" if ok else "FAIL") + "\n",
                encoding="ascii",
            )
            print("SUPERVISOR_REJOIN=" + ("PASS" if ok else "FAIL"), flush=True)
            return 0 if ok else 1
        time.sleep(interval)
    print("SUPERVISOR_REJOIN=TIMEOUT", flush=True)
    return 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--namespace", required=True)
    parser.add_argument("--interface", default="meshB")
    parser.add_argument("--ctrl", required=True)
    parser.add_argument("--network", type=int, default=0)
    parser.add_argument("--ready-file", type=Path, required=True)
    parser.add_argument("--receipt-file", type=Path, required=True)
    parser.add_argument("--budget-seconds", type=float, default=35.0)
    parser.add_argument("--poll-seconds", type=float, default=0.10)
    args = parser.parse_args()
    if not 5 <= args.budget_seconds <= 120:
        parser.error("budget must be 5..120 seconds")
    if not 0.05 <= args.poll_seconds <= 1:
        parser.error("poll interval must be 0.05..1 seconds")
    try:
        return supervise(args.namespace, args.interface, args.ctrl, args.network,
                         args.ready_file, args.receipt_file,
                         args.budget_seconds, args.poll_seconds)
    except (OSError, subprocess.SubprocessError, RuntimeError, ValueError) as exc:
        print("SUPERVISOR_REJOIN=ERROR:" + type(exc).__name__, file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
