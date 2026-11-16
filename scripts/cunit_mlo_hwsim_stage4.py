#!/usr/bin/env python3
"""Stage-4 segmented upstream hostap MLO hwsim execution on an isolated VM.

Runs existing upstream start.sh, run-tests.py and stop.sh separately, with
per-phase time budgets and process-group cleanup. Only sanitized metrics are
uploaded by CI. Raw hostap logs remain in the disposable runner's private dir.
This NEVER establishes C-unit RF or acceptance-v2 success.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import time

# The nearby existing runner owns test allowlists and conservative verdicts.
if __package__:
    from . import cunit_mlo_hwsim_runner as common
else:
    import cunit_mlo_hwsim_runner as common

BASELINE = "ap_open"
PHASE_TIMEOUTS = {"start": 90, "baseline": 65, "test": 100, "stop": 25}
ALLOWED_TESTS = common.SMOKE_TESTS + (common.WIDE_TEST,)


def read_safe_tail(path: Path, limit: int = 1024 * 1024) -> str:
    """Read private log internally; never put its contents into CI output."""
    try:
        with path.open("rb") as f:
            f.seek(0, 2)
            size = f.tell()
            f.seek(max(0, size - limit))
            return f.read().decode("utf-8", errors="replace")
    except OSError:
        return ""


def phase_markers(output: str) -> dict:
    """Only coarse milestones without SSID, MAC, IP, interface or raw lines."""
    return {
        "start_line_seen": bool(re.search(r"(?m)^START (?:eht_mld_|cunit_mlo_|ap_open)", output)),
        "pass_line_seen": bool(re.search(r"(?m)^PASS (?:eht_mld_|cunit_mlo_|ap_open)", output)),
        "failure_line_seen": bool(re.search(r"(?m)^(?:FAIL|SKIP) (?:eht_mld_|cunit_mlo_|ap_open)", output)),
        "association_events": output.count("CTRL-EVENT-CONNECTED"),
        "ap_enabled_events": output.count("AP-ENABLED"),
        "observed_mlo_link_bitmaps": [
            "0x" + m.lower() for m in
            re.findall(r"(?:valid_links|active_links)=0x([0-9a-fA-F]+) via MLO_STATUS:",
                       output)[-4:]
        ],
    }


def classify_startup_errors(output: str) -> dict:
    """Predefined categories only: never publish raw commands, paths or MACs."""
    patterns = {
        "hwsim_module_load": r"(?:modprobe: FATAL|mac80211_hwsim.*(?:failed|error|not found))",
        "permission_denied": r"(?:Operation not permitted|Permission denied)",
        "device_busy": r"(?:Device or resource busy|already in use)",
        "missing_command_or_file": r"(?:command not found|No such file or directory)",
        "invalid_kernel_parameter": r"(?:Invalid argument|unknown parameter)",
        "wpa_control_socket": r"Could not connect to /tmp/wpas-wlan[0-9]+",
        "hostapd_control_socket": r"Could not connect to /var/run/hostapd-global",
        "radius_control_socket": r"Could not connect to hostapd-as-RADIUS-server",
        "supplicant_start": r"(?:wpa_supplicant.*(?:failed|error)|Failed to start wpa_supplicant)",
        "hostapd_start": r"(?:hostapd.*(?:failed|error)|Failed to start hostapd)",
        "rfkill": r"(?:rfkill.*(?:failed|error|blocked))",
        "netlink": r"(?:nl80211.*(?:failed|error)|netlink.*(?:failed|error))",
    }
    return {"error_classes": sorted(
        name for name, pattern in patterns.items()
        if re.search(pattern, output, flags=re.IGNORECASE)
    ), "output_lines": len(output.splitlines())}


def execute_phase(name: str, args: list[str], *, cwd: Path, out: Path,
                  seconds: int, env: dict[str, str]) -> tuple[int, str, dict]:
    """Kill a whole descendant process group on timeout, not just its shell."""
    logfile = out / (name + ".private.log")
    begun = time.monotonic()
    print("CUNIT_MLO_STAGE_START=" + name, flush=True)
    timeout_occurred = False
    rc = 125
    with logfile.open("wb") as log:
        proc = subprocess.Popen(args, cwd=cwd, stdout=log, stderr=subprocess.STDOUT,
                                env=env, start_new_session=True)
        try:
            rc = proc.wait(timeout=seconds)
        except subprocess.TimeoutExpired:
            timeout_occurred = True
            try:
                os.killpg(proc.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                try:
                    os.killpg(proc.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                proc.wait(timeout=5)
            rc = 124
    output = read_safe_tail(logfile)
    info = {
        "phase": name,
        "elapsed_sec": round(time.monotonic() - begun, 2),
        "returncode": rc,
        "timed_out": timeout_occurred,
        "markers": phase_markers(output),
    }
    print("CUNIT_MLO_STAGE_END=%s rc=%d timed_out=%s seconds=%.2f" %
          (name, rc, str(timeout_occurred).lower(), info["elapsed_sec"]), flush=True)
    return rc, output, info


def kernel_info() -> dict:
    """Public non-sensitive kernel capability comparison; no full config dump."""
    release = os.uname().release
    params = common.execute(["modinfo", "-p", "mac80211_hwsim"], timeout=10)
    values = {}
    for key in ("mlo", "multi_radio", "channels"):
        m = re.search(r"(?m)^" + re.escape(key) + r":([^\n]*)", params.stdout)
        values[key] = m is not None
    kernel_config = {}
    paths = [Path("/proc/config.gz"), Path("/boot/config-" + release)]
    for path in paths:
        try:
            if path.suffix == ".gz":
                import gzip
                with gzip.open(path, "rt") as f:
                    data = f.read()
            else:
                data = path.read_text()
            for key in ("CONFIG_MAC80211", "CONFIG_MAC80211_HWSIM",
                        "CONFIG_CFG80211", "CONFIG_MAC80211_DEBUGFS"):
                match = re.search(r"(?m)^" + key + r"=(\w+)$", data)
                kernel_config[key] = match.group(1) if match else "not-set"
            break
        except OSError:
            continue
    return {
        "kernel": release,
        "hwsim_parameters_present": values,
        "kernel_config": kernel_config,
        "python": sys.version.split()[0],
        "hostap": "chromiumos-hostap-f1e9b5086718",
    }


def virtual_runtime_inventory() -> dict:
    """Observe simulator state via counts, never expose actual interface identifiers."""
    commands = {
        "phy_count": (["iw", "phy"], r"(?m)^Wiphy\s+"),
        "netdev_count": (["iw", "dev"], r"(?m)^\s*Interface\s+"),
        "hostapd_processes": (["pgrep", "-xc", "hostapd"], None),
        "wpa_supplicant_processes": (["pgrep", "-xc", "wpa_supplicant"], None),
    }
    data = {"hwsim_module_loaded": Path("/sys/module/mac80211_hwsim").exists()}
    for name, (argv, pattern) in commands.items():
        try:
            p = subprocess.run(argv, text=True, capture_output=True, timeout=5,
                               check=False)
            if pattern:
                data[name] = len(re.findall(pattern, p.stdout)) if p.returncode == 0 else None
            else:
                data[name] = int(p.stdout.strip()) if p.stdout.strip().isdigit() else 0
        except (OSError, subprocess.TimeoutExpired):
            data[name] = None
    return data


def run_isolated(hostap_tree: Path, output_dir: Path, tests: list[str],
                 sim_country: str | None = None) -> dict:
    if os.environ.get("CUNIT_MLO_ISOLATED_VM") != "YES" or os.geteuid() != 0:
        raise RuntimeError("root on explicit CUNIT_MLO_ISOLATED_VM=YES VM required")
    if not tests or any(t not in ALLOWED_TESTS for t in tests):
        raise RuntimeError("unsupported test selection")
    os.umask(0o077)
    output_dir.mkdir(mode=0o700, parents=True, exist_ok=False)
    suite = hostap_tree / "tests/hwsim"
    probe = common.vm_probe(hostap_tree)
    (output_dir / "kernel.json").write_text(json.dumps(kernel_info(), indent=2) + "\n")
    (output_dir / "preflight.json").write_text(json.dumps(probe, indent=2) + "\n")
    phases, results, diagnostics = [], {}, {}
    preflight_ok = probe["status"] == "READY"
    if preflight_ok:
        for file in ("start.sh", "run-tests.py", "stop.sh"):
            if not (suite / file).is_file():
                preflight_ok = False
                probe["status"] = "BLOCKED"
                probe["reasons"].append("missing upstream phase executable: " + file)
    env = dict(os.environ)
    private_logs = output_dir / "upstream-logs"
    private_logs.mkdir(exist_ok=True, mode=0o700)
    env["LOGDIR"] = str(private_logs)
    started = False
    baseline_ok = False
    ip_ping = None
    try:
        if preflight_ok:
            # Upstream run-all.sh passes 'channels=2' to the same start.sh.
            rc, output, info = execute_phase(
                "start", [str(suite / "start.sh"), "channels=2"],
                cwd=suite, out=output_dir, seconds=PHASE_TIMEOUTS["start"], env=env)
            phases.append(info)
            info["post_start_inventory"] = virtual_runtime_inventory()
            if rc == 0:
                started = True
            else:
                diagnostics["start"] = {
                    **common.sanitized_failure_diagnostics(output, rc),
                    **classify_startup_errors(output),
                }
        if started:
            rc, output, info = execute_phase(
                "baseline", [str(suite / "run-tests.py"), "-D", "-q",
                             "--logdir", str(private_logs), BASELINE],
                cwd=suite, out=output_dir, seconds=PHASE_TIMEOUTS["baseline"], env=env)
            phases.append(info)
            baseline_ok = common.completed_test(output, BASELINE, rc)
            if not baseline_ok:
                diagnostics["baseline"] = common.sanitized_failure_diagnostics(output, rc)
        if baseline_ok:
            if common.WIDE_TEST in tests:
                from shutil import copyfile
                fixture = Path(__file__).parent / "hwsim/test_cunit_mlo.py"
                copyfile(fixture, suite / "test_cunit_mlo.py")
            if sim_country:
                reg = common.execute(["iw", "reg", "set", sim_country], timeout=15)
                if reg.returncode:
                    diagnostics["regulatory"] = {"returncode": reg.returncode}
                    baseline_ok = False
            if baseline_ok:
                for test in tests:
                    rc, output, info = execute_phase(
                        test, [str(suite / "run-tests.py"), "-D", "-q",
                               "--logdir", str(private_logs), test],
                        cwd=suite, out=output_dir, seconds=PHASE_TIMEOUTS["test"], env=env)
                    phases.append(info)
                    results[test] = ("SMOKE_PASS" if common.completed_test(output, test, rc)
                                     else "FAILED")
                    if results[test] != "SMOKE_PASS":
                        diagnostics[test] = common.sanitized_failure_diagnostics(output, rc)
                        break
                    if test == common.WIDE_TEST:
                        ip_ping = common.parse_ip_ping_marker(output)
    finally:
        if preflight_ok:
            # Even if start partially configured the simulator, always attempt
            # upstream cleanup, bounded separately from association timeouts.
            try:
                rc, output, info = execute_phase(
                    "stop", [str(suite / "stop.sh")], cwd=suite, out=output_dir,
                    seconds=PHASE_TIMEOUTS["stop"], env=env)
                phases.append(info)
                if rc:
                    diagnostics["stop"] = {"returncode": rc, "timed_out": rc == 124}
            except OSError:
                diagnostics["stop"] = {"returncode": 125, "timed_out": False}
    summary = common.sanitized_summary(probe, results, ip_ping, diagnostics)
    summary["phase_trace"] = phases
    summary["baseline"] = "PASS" if baseline_ok else "FAILED_OR_NOT_RUN"
    summary["expected_tests"] = tests
    summary["observed_tests"] = len(results)
    if not baseline_ok or any(p["returncode"] != 0 for p in phases if p["phase"] == "stop"):
        summary["status"] = "INCOMPLETE"
    if len(results) != len(tests):
        summary["status"] = "INCOMPLETE" if preflight_ok else "BLOCKED"
    (output_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    return summary


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--hostap-tree", type=Path, required=True)
    p.add_argument("--output-dir", type=Path, required=True)
    p.add_argument("--tests", nargs="+", choices=ALLOWED_TESTS, required=True)
    p.add_argument("--sim-country", choices=("CA", "US"))
    args = p.parse_args(argv)
    try:
        result = run_isolated(args.hostap_tree, args.output_dir, args.tests, args.sim_country)
    except (RuntimeError, OSError) as error:
        # Error messages may carry private filesystem locations; redact them.
        print("CUNIT_MLO_STAGE4=BLOCKED exception=" + type(error).__name__)
        return 2
    print(json.dumps(result, sort_keys=True), flush=True)
    return 0 if result["status"] in ("UPSTREAM_MLD_SMOKE_PASS",
                                     "WIDE_MLD_SMOKE_PASS",
                                     "WIDE_MLD_IP_PASS") else 2


if __name__ == "__main__":
    raise SystemExit(main())
