#!/usr/bin/env python3
"""Run REAL upstream hostap MLO tests on an explicitly isolated Linux VM.

This is not an acceptance-evidence generator. A passing upstream MLD smoke
case establishes only the scope exercised by that case, never HWSIM_PASS.
No device-specific credentials, MACs or raw captures are published.
"""

import argparse
import datetime as dt
import hashlib
import importlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

SMOKE_TESTS = (
    "eht_mld_owe_two_links",
    "eht_mld_link_removal",
    "eht_mld_disassociate",
    "eht_mld_deauthenticate",
)
WIDE_TEST = "cunit_mlo_5g160_6g160"
KNOWN_TESTS = SMOKE_TESTS + (WIDE_TEST,)


def execute(command, *, cwd=None, timeout=20, env=None):
    try:
        return subprocess.run(command, cwd=cwd, env=env, text=True,
                              stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                              timeout=timeout, check=False)
    except (OSError, subprocess.TimeoutExpired) as error:
        return subprocess.CompletedProcess(command, 124, stdout=str(error))


def physical_wifi_present(root=Path("/sys/class/ieee80211")):
    """Conservatively reject a VM that exposes any existing non-hwsim PHY."""
    for phy in root.glob("phy*"):
        driver = phy / "device" / "driver"
        if not driver.is_symlink() or "mac80211_hwsim" not in str(driver.resolve()):
            return True
    return False


def crypto_test_dependency_available():
    """hostap's complete hwsim test discovery imports PyCryptodome modules."""
    for name in ("Cryptodome.Cipher", "Crypto.Cipher"):
        try:
            importlib.import_module(name)
            return True
        except ImportError:
            continue
    return False


def vm_probe(hostap_tree=None, *, module_info=None, caps_text=None,
             osroot=Path("/sys/class/ieee80211"), which=shutil.which,
             crypto_available=None):
    """Read-only preflight. Structured BLOCKED rather than guessed success."""
    reasons = []
    module = (module_info if module_info is not None else
              execute(["modinfo", "-p", "mac80211_hwsim"]).stdout)
    params = set(re.findall(r"(?m)^([a-zA-Z_][a-zA-Z0-9_]*):", module))
    if "mlo" not in params:
        reasons.append("kernel module mac80211_hwsim lacks MLO parameter")
    if "multi_radio" not in params:
        reasons.append("kernel module mac80211_hwsim lacks multi_radio parameter")
    caps = caps_text
    if caps is None:
        try:
            caps = Path("/proc/self/status").read_text(encoding="ascii")
        except OSError:
            caps = ""
    match = re.search(r"(?m)^CapEff:\s*([0-9a-fA-F]+)$", caps)
    if not match or not (int(match.group(1), 16) & (1 << 12)):
        reasons.append("CAP_NET_ADMIN unavailable; cannot configure virtual radios")
    if physical_wifi_present(osroot):
        reasons.append("physical/unknown Wi-Fi PHY detected: refuse simulated RF setup")
    if crypto_available is None:
        crypto_available = crypto_test_dependency_available()
    if not crypto_available:
        reasons.append("Python PyCryptodome dependency missing; install python3-pycryptodome")
    for cmd in ("ip", "modprobe", "iw"):
        if not which(cmd):
            reasons.append(f"required command missing: {cmd}")
    if hostap_tree is not None:
        tests_dir = Path(hostap_tree) / "tests" / "hwsim"
        if not (tests_dir / "run-all.sh").is_file():
            reasons.append("hostap hwsim run-all.sh unavailable")
        if not (tests_dir / "test_eht.py").is_file():
            reasons.append("hostap EHT MLD tests unavailable")
    return {"status": "READY" if not reasons else "BLOCKED",
            "kernel": os.uname().release,
            "hwsim_module_parameters": sorted(params & {"mlo", "multi_radio", "channels"}),
            "reasons": reasons}


def upstream_test_command(suite, test):
    """Use hostap run-all.sh documented --channels option, not a test name."""
    if test not in KNOWN_TESTS:
        raise ValueError("unknown MLD test")
    return [str(suite / "run-all.sh"), "--channels", "2", test]


def completed_test(output, test, returncode):
    """An actual runner must exit zero AND show an exact test PASS line."""
    # Some hostap versions include timestamps after PASS; do not match substrings.
    passline = re.search(r"(?m)^PASS " + re.escape(test) + r"(?:\s|$)", output)
    badline = re.search(r"(?m)^(?:FAIL|SKIP|NOTRUN) " + re.escape(test) + r"(?:\s|$)", output)
    return returncode == 0 and passline is not None and badline is None


def parse_ip_ping_marker(output):
    """Extract observed packets only from the fixture's explicit success line."""
    marker = re.search(
        r"(?m)^CUNIT_MLO_IP_BIDIRECTIONAL_PASS "
        r"tx_sta=(\d+) rx_sta=(\d+) tx_ap=(\d+) rx_ap=(\d+)\s*$",
        output)
    if not marker:
        return None
    sent_sta, received_sta, sent_ap, received_ap = map(int, marker.groups())
    if (not 0 < received_sta <= sent_sta <= 1000 or
            not 0 < received_ap <= sent_ap <= 1000):
        return None
    return {"sta_to_ap": {"sent": sent_sta, "received": received_sta},
            "ap_to_sta": {"sent": sent_ap, "received": received_ap}}


def sanitized_summary(probe, results, ip_ping=None):
    """A summary with no identifiers or raw logs; NOT an HWSIM_PASS verdict."""
    if probe["status"] != "READY":
        state = "BLOCKED"
    elif all(value == "SMOKE_PASS" for value in results.values()) and results:
        state = (("WIDE_MLD_IP_PASS" if ip_ping else "WIDE_MLD_SMOKE_PASS")
                 if WIDE_TEST in results else "UPSTREAM_MLD_SMOKE_PASS")
    else:
        state = "INCOMPLETE"
    return {"status": state, "kernel": probe["kernel"], "tests": results,
            "first_failed_test": next((name for name, state in results.items()
                                       if state != "SMOKE_PASS"), None),
            "acceptance_v2": "NOT_PROVEN", "ip_ping": ip_ping,
            "note": "No per-link counter/failure-cycle evidence; not HWSIM_PASS"}


def run_tests(hostap_tree, output_dir, tests, fixture_source, sim_country=None):
    if os.environ.get("CUNIT_MLO_ISOLATED_VM") != "YES":
        raise RuntimeError("CUNIT_MLO_ISOLATED_VM=YES is required on dedicated VM")
    if os.geteuid() != 0:
        raise RuntimeError("root required to run upstream hwsim virtual networking tests")
    probe = vm_probe(hostap_tree)
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "preflight.json").write_text(json.dumps(probe, indent=2) + "\n")
    if probe["status"] != "READY":
        summary = sanitized_summary(probe, {})
        (output_dir / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
        return summary
    suite = hostap_tree / "tests" / "hwsim"
    if WIDE_TEST in tests:
        # Upstream test runner discovers test_*.py in its directory.
        shutil.copyfile(fixture_source, suite / "test_cunit_mlo.py")
    if sim_country:
        # Only an isolated VM with NO physical radio passed the preflight.
        result = execute(["iw", "reg", "set", sim_country], timeout=15)
        if result.returncode:
            raise RuntimeError("simulated VM regulatory setup failed")
    results = {}
    ip_ping = None
    for test in tests:
        # Bound each test including hostap startup/stop; preserve raw output locally.
        result = execute(["timeout", "--kill-after=5s", "240s",
                          *upstream_test_command(suite, test)],
                         cwd=suite, timeout=250)
        # Raw logs are local-only, possibly contain virtual MACs, test SSIDs.
        logfile = output_dir / (test + ".private.log")
        logfile.write_text(result.stdout, encoding="utf-8")
        results[test] = ("SMOKE_PASS" if completed_test(result.stdout, test,
                                                       result.returncode) else "FAILED")
        if test == WIDE_TEST and results[test] == "SMOKE_PASS":
            ip_ping = parse_ip_ping_marker(result.stdout)
        if results[test] == "FAILED":
            # Stop at first failure instead of burning the CI job timeout.
            break
    summary = sanitized_summary(probe, results, ip_ping)
    (output_dir / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    return summary


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=["probe", "run"])
    parser.add_argument("--hostap-tree", type=Path)
    parser.add_argument("--output-dir", type=Path, default=Path("/tmp/cunit-mlo-host"))
    parser.add_argument("--tests", nargs="+", choices=KNOWN_TESTS,
                        default=[SMOKE_TESTS[0]])
    parser.add_argument("--sim-country", choices=["CA", "US"],
                        help="VM-only synthetic regulatory region (never on physical radio)")
    args = parser.parse_args(argv)
    if args.mode == "probe":
        status = vm_probe(args.hostap_tree)
        print(json.dumps(status, sort_keys=True))
        return 0 if status["status"] == "READY" else 2
    if not args.hostap_tree:
        parser.error("--hostap-tree is mandatory for run")
    try:
        summary = run_tests(args.hostap_tree, args.output_dir, args.tests,
                            Path(__file__).parent / "hwsim" / "test_cunit_mlo.py",
                            args.sim_country)
    except (RuntimeError, OSError) as error:
        print(json.dumps({"status": "BLOCKED", "reason": str(error),
                          "acceptance_v2": "NOT_PROVEN"}, sort_keys=True))
        return 2
    print(json.dumps(summary, sort_keys=True))
    return 0 if summary["status"] in ("UPSTREAM_MLD_SMOKE_PASS",
                                      "WIDE_MLD_SMOKE_PASS",
                                      "WIDE_MLD_IP_PASS") else 2


if __name__ == "__main__":
    raise SystemExit(main())
