#!/usr/bin/env python3
"""Offline-only, redacted phase classifier for C-unit UART captured during G1 test.

Never forwards, stores or prints raw UART, firmware identifiers or boot arguments.
This tool is deliberately not a fault-cause classifier.
"""
from __future__ import annotations
import argparse, hashlib, json, re
from pathlib import Path

KNOWN_LOG_SHA = "0dda7a227a36bf6c8e5af418bdbd35c5001158ece52acc42b2b583547b791a90"
MAX_LOG_BYTES = 4 * 1024 * 1024
TOKEN_PATTERNS = {
    "atf_el3_exit": rb"el3_exit|Preparing for EL3 exit to normal world",
    "kernel_el2": rb"Kernel_EL\s*2",
    "linux_banner": rb"Linux version\s",
    "loader_init": rb"TERMINAL6_LOADER_INIT_STARTED",
    "loader_ready": rb"TERMINAL6_LOADER_READY",
    "loader_ssh": rb"TERMINAL6_LOADER_ISOLATED_SSH_STARTED",
}
WATCHDOG = rb"CPU\(0\) in ATF by WDT|HW_WDT"

def summarize(data: bytes) -> dict:
    w = re.search(WATCHDOG, data, re.I)
    before = data[:w.start()] if w else data
    flags = {name: bool(re.search(pattern, before, re.I))
             for name, pattern in TOKEN_PATTERNS.items()}
    if w and flags["atf_el3_exit"] and not flags["linux_banner"] and not flags["loader_init"]:
        verdict = "EL3_TO_FIRST_LINUX_OUTPUT_UNPROVEN_WDT_OBSERVED"
    elif flags["loader_ready"]:
        verdict = "LOADER_READY_MARKER_OBSERVED_BEFORE_FIRST_WDT"
    elif w:
        verdict = "WDT_OBSERVED_PHASE_UNRESOLVED"
    else:
        verdict = "NO_WDT_MARKER_FOUND_PHASE_UNRESOLVED"
    return {
      "schema":"terminal6-loader-uart-g1-v1",
      "log_bytes":len(data),
      "log_sha256":hashlib.sha256(data).hexdigest(),
      "watchdog_marker_present":w is not None,
      "pre_first_watchdog_markers":flags,
      "verdict":verdict,
      "scope":"string-markers only; absence may be UART loss; no root-cause assertion",
      "safety":"no raw UART output; post-WDT stock B Linux banner excluded"
    }

def main():
    p=argparse.ArgumentParser()
    p.add_argument("uart_log",type=Path)
    p.add_argument("--require-20261121-exact-sha",action="store_true")
    args=p.parse_args()
    path=args.uart_log
    if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_LOG_BYTES:
        raise SystemExit("invalid UART log path or size")
    data=path.read_bytes()
    report=summarize(data)
    if args.require_20261121_exact_sha and report["log_sha256"]!=KNOWN_LOG_SHA:
        raise SystemExit("UART_LOG_SHA_MISMATCH; report not trusted")
    print(json.dumps(report,indent=2,sort_keys=True))
if __name__=="__main__":
    main()
