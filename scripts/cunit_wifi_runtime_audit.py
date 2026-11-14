#!/usr/bin/env python3
"""Collect a privacy-filtered, read-only Wi-Fi runtime snapshot.

This tool does not configure regulatory state, create interfaces, start APs,
scan, associate, or transmit. It deliberately reports advertisements and
observations separately from authorization or functional PASS claims.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import stat
import subprocess
import sys
from pathlib import Path
from typing import Callable


Runner = Callable[[list[str]], tuple[int, str]]


def run_command(argv: list[str]) -> tuple[int, str]:
    try:
        result = subprocess.run(argv, text=True, stdout=subprocess.PIPE,
                                stderr=subprocess.DEVNULL, timeout=8,
                                check=False)
        return result.returncode, result.stdout
    except (OSError, subprocess.TimeoutExpired):
        return 127, ""


def _cmd(runner: Runner, *argv: str) -> str:
    rc, output = runner(list(argv))
    return output if rc == 0 else ""


def _interfaces(iw_dev: str) -> list[dict[str, object]]:
    result: list[dict[str, object]] = []
    current: dict[str, object] | None = None
    for line in iw_dev.splitlines():
        m = re.match(r"\s*Interface\s+(\S+)", line)
        if m:
            current = {"name": m.group(1), "type": None,
                       "channel_mhz": None, "ssid_present": False}
            result.append(current)
            continue
        if current is None:
            continue
        m = re.match(r"\s*type\s+(\S+)", line)
        if m:
            current["type"] = m.group(1)
        m = re.match(r"\s*channel\s+\d+\s+\((\d+)\s+MHz\)", line)
        if m:
            current["channel_mhz"] = int(m.group(1))
        if re.match(r"\s*ssid\s+", line):
            current["ssid_present"] = True
    return result


def _regulatory(reg: str) -> dict[str, object]:
    countries = re.findall(r"^country\s+([A-Z0-9]{2}):", reg, re.M)
    global_match = re.search(
        r"^global\s*\n\s*country\s+([A-Z0-9]{2}):", reg, re.M
    )
    ranges: list[tuple[int, int]] = []
    for line in reg.splitlines():
        if re.search(r"\(\s*(?:N/A|\d+)\s*,\s*\d+\s*\)", line):
            m = re.search(r"\(\s*(\d+)\s*-\s*(\d+)\s*@", line)
            if m:
                lo, hi = int(m.group(1)), int(m.group(2))
                if hi >= 5925 and lo <= 6425:
                    ranges.append((lo, hi))
    return {
        "country_codes": sorted(set(countries)),
        "global_country_code": global_match.group(1) if global_match else None,
        "rules_overlapping_japan_6ghz_mhz": [list(x) for x in ranges],
        # A driver/regdb state never proves that this board is certified for
        # the selected operating class, antenna, power, or installation.
        "rf_authorization_established": False,
    }


def _inside_reg_rule(freq_mhz: int, ranges: list[list[int]]) -> bool:
    return any(lo <= freq_mhz <= hi for lo, hi in ranges)


def _phy_records(iw_phy: str, regulatory: dict[str, object]) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    current: dict[str, object] | None = None
    band_num: int | None = None
    ranges = regulatory["rules_overlapping_japan_6ghz_mhz"]
    assert isinstance(ranges, list)
    japan_rules_active = regulatory["global_country_code"] == "JP"
    for line in iw_phy.splitlines():
        m = re.match(r"Wiphy\s+(\S+)", line)
        if m:
            current = {"name": m.group(1), "bands_advertised": set(),
                       "six_ghz_channels": [], "eht_capability_advertised": False,
                       "mlo_keyword_observed": False}
            records.append(current)
            band_num = None
            continue
        if current is None:
            continue
        m = re.match(r"\s*Band\s+(\d+):", line)
        if m:
            band_num = int(m.group(1))
            continue
        if "EHT" in line:
            current["eht_capability_advertised"] = True
        if re.search(r"\bMLO\b|Multi[- ]Link", line, re.I):
            current["mlo_keyword_observed"] = True
        m = re.search(r"(\d{4,5})\s+MHz\s+\[(\d+)\](.*)$", line)
        if not m:
            continue
        freq = int(float(m.group(1)))
        flags = m.group(3).lower()
        band = ("2.4GHz" if 2400 <= freq < 2500 else
                "5GHz" if 4900 <= freq < 5925 else
                "6GHz" if 5925 <= freq <= 7125 else None)
        if band:
            bands = current["bands_advertised"]
            assert isinstance(bands, set)
            bands.add(band)
        if 5925 <= freq <= 6425:
            blocked = any(flag in flags for flag in ("disabled", "no ir", "radar"))
            channel = {
                "frequency_mhz": freq,
                "channel": int(m.group(2)),
                "disabled_or_no_ir_or_radar": blocked,
                "within_current_regulatory_rule": japan_rules_active and _inside_reg_rule(freq, ranges),
            }
            channels = current["six_ghz_channels"]
            assert isinstance(channels, list)
            channels.append(channel)
    for record in records:
        bands = record["bands_advertised"]
        record["bands_advertised"] = sorted(bands) if isinstance(bands, set) else []
        channels = record["six_ghz_channels"]
        assert isinstance(channels, list)
        record["six_ghz_linux_rule_candidate_count"] = sum(
            not c["disabled_or_no_ir_or_radar"] and c["within_current_regulatory_rule"]
            for c in channels
        )
        record["six_ghz_rf_start_permitted"] = False
    return records


def _station_info(runner: Runner, interfaces: list[dict[str, object]]) -> list[dict[str, object]]:
    stations: list[dict[str, object]] = []
    for interface in interfaces:
        name = interface["name"]
        assert isinstance(name, str)
        raw = _cmd(runner, "iw", "dev", name, "station", "dump")
        blocks = re.split(r"(?=^Station\s)", raw, flags=re.M)
        for block in blocks:
            if not re.search(r"^Station\s+\S+", block, re.M):
                continue
            rates = re.findall(r"(?:tx|rx) bitrate:\s*([^\n]+)", block, re.I)
            link_ids = sorted({int(x) for x in re.findall(r"\blink id:\s*(\d+)", block, re.I)})
            stations.append({
                "interface": name,
                "rate_modes_observed": sorted({
                    mode for mode in ("EHT", "HE", "VHT", "HT")
                    if any(re.search(rf"(?<![A-Z]){mode}(?:-|\s)", rate.upper())
                           for rate in rates)
                }),
                "link_ids_observed": link_ids,
                "rx_bytes_present": bool(re.search(r"^\s*rx bytes:\s*\d+", block, re.M)),
                "tx_bytes_present": bool(re.search(r"^\s*tx bytes:\s*\d+", block, re.M)),
            })
    return stations


def _pci_inventory(sys_root: Path) -> list[dict[str, str]]:
    result: list[dict[str, str]] = []
    for entry in sorted((sys_root / "bus/pci/devices").glob("*")):
        try:
            vendor = (entry / "vendor").read_text().strip().lower()
            device = (entry / "device").read_text().strip().lower()
        except OSError:
            continue
        if vendor != "0x14c3" or device not in {"0x7990", "0x7991", "0x7993", "0x799b"}:
            continue
        driver = "unknown"
        try:
            driver = (entry / "driver").resolve().name
        except OSError:
            pass
        result.append({"vendor": vendor, "device": device, "driver": driver})
    return result


def _diagnostic_markers(kernel_log: str) -> dict[str, bool]:
    log = kernel_log.lower()
    return {
        "regulatory_database_missing_seen": "regulatory.db" in log and any(
            token in log for token in ("failed", "missing", "not found", "no such file")
        ),
        "eeprom_fallback_seen": "eeprom load fail, use default bin" in log,
        "mcu_timeout_seen": bool(re.search(r"mcu.*(?:timeout|timed out)|(?:timeout|timed out).*mcu", log)),
        "pcie_correctable_aer_seen": "correctable aer" in log or "aer: corrected" in log,
    }


def collect(runner: Runner = run_command, sys_root: Path = Path("/sys")) -> dict[str, object]:
    kernel = _cmd(runner, "uname", "-r").strip() or None
    regulatory_text = _cmd(runner, "iw", "reg", "get")
    reg = _regulatory(regulatory_text)
    phy_text = _cmd(runner, "iw", "phy")
    dev_text = _cmd(runner, "iw", "dev")
    interfaces = _interfaces(dev_text)
    return {
        "schema": 1,
        "collected_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "kernel_release": kernel,
        "pci_wifi_endpoints": _pci_inventory(sys_root),
        "regulatory": reg,
        "wiphys": _phy_records(phy_text, reg),
        "interfaces": interfaces,
        "associated_stations": _station_info(runner, interfaces),
        "diagnostic_markers": _diagnostic_markers(_cmd(runner, "dmesg")),
        "limitations": [
            "read-only snapshot; this tool does not authorize RF transmission",
            "EHT fields are capability/rate observations, not throughput proof",
            "MLO success requires one MLD session with multiple active links and IP traffic",
            "6GHz operation additionally requires verified equipment certification and operating conditions",
        ],
    }


def write_private_json(path: Path, report: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    fd = os.open(path, flags, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(report, stream, indent=2, sort_keys=True)
            stream.write("\n")
        os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)
    except BaseException:
        try:
            os.unlink(path)
        except OSError:
            pass
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="write JSON with mode 0600")
    args = parser.parse_args()
    report = collect()
    if args.output:
        write_private_json(args.output, report)
    else:
        sys.stdout.write(json.dumps(report, indent=2, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
