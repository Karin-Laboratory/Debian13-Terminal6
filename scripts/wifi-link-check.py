#!/usr/bin/env python3
"""Read-only, per-band C-unit Wi-Fi STA smoke check.

This intentionally does not change interface state, addresses, routes, DNS,
supplicant configuration, or persistent files. Output excludes SSID, BSSID,
MAC, IP addresses, DNS answers, and credentials.
"""
from __future__ import annotations

import argparse
import ipaddress
import json
import re
import shutil
import subprocess
import sys
import time
from typing import Any


class CheckError(RuntimeError):
    pass


def validate_inputs(args: argparse.Namespace) -> None:
    iface_re = re.compile(r"^[A-Za-z0-9_.-]{1,15}$")
    for value in (args.iface, args.management_if):
        if not iface_re.fullmatch(value):
            raise CheckError("invalid network interface name")
    for value in (args.gateway, args.dns_server):
        try:
            ipaddress.IPv4Address(value)
        except ipaddress.AddressValueError:
            raise CheckError("gateway and DNS server must be IPv4 literals") from None
    if args.throughput_server:
        try:
            ipaddress.IPv4Address(args.throughput_server)
        except ipaddress.AddressValueError:
            raise CheckError("throughput server must be an IPv4 literal") from None
    domain = args.domain.rstrip(".")
    labels = domain.split(".")
    if len(domain) > 253 or not labels or any(
        not re.fullmatch(r"(?=.{1,63}$)[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?", label)
        for label in labels
    ):
        raise CheckError("invalid DNS query name")


def run(argv: list[str], timeout: int = 10) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(argv, capture_output=True, text=True, timeout=timeout, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise CheckError(f"command failed: {argv[0]} ({exc.__class__.__name__})") from None


def json_command(argv: list[str]) -> Any:
    result = run(argv)
    if result.returncode:
        raise CheckError(f"command failed: {argv[0]}")
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        raise CheckError(f"invalid JSON from {argv[0]}") from None


def interface_ipv4(iface: str) -> str:
    devices = json_command(["ip", "-j", "-4", "address", "show", "dev", iface])
    for device in devices:
        for address in device.get("addr_info", []):
            if address.get("family") == "inet" and address.get("scope") == "global":
                value = address.get("local", "")
                if value and not value.startswith("169.254."):
                    return value
    raise CheckError("STA interface has no global IPv4 address")


def band_frequency_ok(band: str, freq: int) -> bool:
    if band == "2.4":
        return 2400 <= freq < 2500
    return 5000 <= freq < 5925


def default_routes() -> list[dict[str, Any]]:
    routes = json_command(["ip", "-j", "-4", "route", "show", "default"])
    return sorted(routes, key=lambda item: json.dumps(item, sort_keys=True))


def route_uses_iface(address: str, source: str, iface: str) -> bool:
    routes = json_command(["ip", "-j", "-4", "route", "get", address, "from", source])
    return bool(routes) and routes[0].get("dev") == iface


def link_info(iface: str, band: str) -> dict[str, Any]:
    result = run(["iw", "dev", iface, "link"])
    if result.returncode or "Connected to " not in result.stdout:
        raise CheckError("STA is not associated")
    match = re.search(r"^\s*freq:\s*(\d+)\s*$", result.stdout, re.MULTILINE)
    if not match:
        raise CheckError("associated frequency is unavailable")
    freq = int(match.group(1))
    if not band_frequency_ok(band, freq):
        raise CheckError("associated frequency does not match requested band")
    return {"associated": True, "frequency_mhz": freq}


def security_info(iface: str, expected: str) -> str:
    result = run(["wpa_cli", "-i", iface, "status"])
    if result.returncode:
        raise CheckError("wpa_supplicant control status unavailable")
    fields = dict(line.split("=", 1) for line in result.stdout.splitlines() if "=" in line)
    if fields.get("wpa_state") != "COMPLETED":
        raise CheckError("supplicant state is not COMPLETED")
    key_mgmt = fields.get("key_mgmt", "")
    accepted = {"wpa2": {"WPA2-PSK"}, "sae": {"SAE"}}
    if expected != "any" and key_mgmt not in accepted[expected]:
        raise CheckError(f"negotiated security does not match requested mode: {expected}")
    if key_mgmt not in {"WPA2-PSK", "SAE", "WPA2-PSK SAE"}:
        raise CheckError("unsupported or unverified negotiated security mode")
    return key_mgmt


def supplicant_completed(iface: str) -> bool:
    result = run(["wpa_cli", "-i", iface, "status"])
    if result.returncode:
        return False
    fields = dict(line.split("=", 1) for line in result.stdout.splitlines() if "=" in line)
    return fields.get("wpa_state") == "COMPLETED"


def exercise_reconnect(iface: str, management_if: str, timeout: int) -> None:
    routes_before = default_routes()
    if not routes_before or any(route.get("dev") != management_if for route in routes_before):
        raise CheckError("refusing reconnect test: default route is not exclusively on management interface")
    if not supplicant_completed(iface):
        raise CheckError("refusing reconnect test: STA is not associated before test")
    disconnected = run(["wpa_cli", "-i", iface, "disconnect"])
    if disconnected.returncode or "OK" not in disconnected.stdout:
        raise CheckError("supplicant refused transient disconnect request")
    drop_deadline = time.monotonic() + 5
    while time.monotonic() < drop_deadline and supplicant_completed(iface):
        time.sleep(0.2)
    if supplicant_completed(iface):
        run(["wpa_cli", "-i", iface, "reconnect"])
        raise CheckError("supplicant did not expose a disconnected state; reconnect was requested for recovery")
    reconnected = run(["wpa_cli", "-i", iface, "reconnect"])
    if reconnected.returncode or "OK" not in reconnected.stdout:
        raise CheckError("supplicant refused reconnect request")
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if supplicant_completed(iface):
            if default_routes() != routes_before:
                raise CheckError("default route changed during reconnect test")
            return
        time.sleep(1)
    run(["wpa_cli", "-i", iface, "reconnect"])
    raise CheckError("STA did not re-associate before reconnect timeout")


def station_stats(iface: str) -> dict[str, int | str]:
    result = run(["iw", "dev", iface, "station", "dump"])
    if result.returncode:
        return {}
    values: dict[str, int | str] = {}
    for key in ("tx packets", "rx packets", "tx retries", "tx failed"):
        match = re.search(rf"^\s*{re.escape(key)}:\s*(\d+)\s*$", result.stdout, re.MULTILINE)
        if match:
            values[key.replace(" ", "_")] = int(match.group(1))
    for key in ("tx bitrate", "rx bitrate"):
        match = re.search(rf"^\s*{re.escape(key)}:\s*(.+?)\s*$", result.stdout, re.MULTILINE)
        if match:
            values[key.replace(" ", "_")] = match.group(1)
    return values


def ping_gateway(iface: str, gateway: str) -> dict[str, float | int]:
    result = run(["ping", "-n", "-I", iface, "-c", "5", "-W", "2", gateway], timeout=15)
    sent = re.search(r"(\d+) packets transmitted", result.stdout)
    received = re.search(r"(\d+) (?:packets )?received", result.stdout)
    rtt = re.search(r"=\s*([0-9.]+)/([0-9.]+)/([0-9.]+)/", result.stdout)
    tx = int(sent.group(1)) if sent else 0
    rx = int(received.group(1)) if received else 0
    if result.returncode or tx != 5 or rx != 5 or not rtt:
        raise CheckError("Wi-Fi-bound gateway ping did not pass 5/5")
    return {"sent": tx, "received": rx, "rtt_avg_ms": float(rtt.group(2))}


def dns_query(iface: str, source: str, server: str, domain: str) -> int:
    result = run(["dig", "+time=2", "+tries=1", "+noall", "+answer", "-b", source,
                  f"@{server}", domain, "A"], timeout=5)
    if result.returncode:
        raise CheckError("DNS query failed")
    answers = [line for line in result.stdout.splitlines() if re.search(r"\sIN\s+A\s+[0-9.]+$", line)]
    if not answers:
        raise CheckError("DNS query returned no A answer")
    return len(answers)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--iface", required=True)
    parser.add_argument("--band", choices=("2.4", "5"), required=True)
    parser.add_argument("--management-if", required=True)
    parser.add_argument("--gateway", required=True)
    parser.add_argument("--dns-server", required=True)
    parser.add_argument("--domain", required=True)
    parser.add_argument("--security", choices=("any", "wpa2", "sae"), default="any")
    parser.add_argument("--exercise-reconnect", action="store_true",
                        help="briefly disconnect/reconnect this STA using wpa_supplicant control")
    parser.add_argument("--reconnect-timeout", type=int, default=30)
    parser.add_argument("--throughput-server", help="optional iperf3 server address on the Wi-Fi path")
    parser.add_argument("--throughput-port", type=int, default=5201)
    args = parser.parse_args()

    needed = ("ip", "iw", "wpa_cli", "ping", "dig")
    missing = [name for name in needed if shutil.which(name) is None]
    if missing:
        print(json.dumps({"result": "FAIL", "reason": "missing_tool", "tools": missing}))
        return 1

    reconnect_attempted = False
    try:
        validate_inputs(args)
        if args.reconnect_timeout < 1 or not 1 <= args.throughput_port <= 65535:
            raise CheckError("invalid reconnect timeout or throughput port")
        routes_before = default_routes()
        if not routes_before or any(route.get("dev") != args.management_if for route in routes_before):
            raise CheckError("default route is absent or not exclusively on management interface")
        wifi = link_info(args.iface, args.band)
        security = security_info(args.iface, args.security)
        if args.exercise_reconnect:
            reconnect_attempted = True
            exercise_reconnect(args.iface, args.management_if, args.reconnect_timeout)
            wifi = link_info(args.iface, args.band)
            security = security_info(args.iface, args.security)
        source = interface_ipv4(args.iface)
        if not route_uses_iface(args.gateway, source, args.iface):
            raise CheckError("gateway route is not bound to Wi-Fi interface")
        if not route_uses_iface(args.dns_server, source, args.iface):
            raise CheckError("DNS-server route is not bound to Wi-Fi interface")
        counters_before = station_stats(args.iface)
        ping = ping_gateway(args.iface, args.gateway)
        answer_count = dns_query(args.iface, source, args.dns_server, args.domain)
        throughput_mbps = None
        if args.throughput_server:
            if shutil.which("iperf3") is None:
                raise CheckError("iperf3 is required when --throughput-server is used")
            if not route_uses_iface(args.throughput_server, source, args.iface):
                raise CheckError("throughput-server route is not bound to Wi-Fi interface")
            result = run(["iperf3", "-c", args.throughput_server, "-p", str(args.throughput_port),
                          "-B", source, "-t", "10", "-J"], timeout=20)
            if result.returncode:
                raise CheckError("iperf3 throughput test failed")
            try:
                throughput_mbps = json.loads(result.stdout)["end"]["sum_received"]["bits_per_second"] / 1_000_000
            except (json.JSONDecodeError, KeyError, TypeError):
                raise CheckError("iperf3 returned an invalid result") from None
        counters_after = station_stats(args.iface)
        routes_after = default_routes()
        if routes_after != routes_before:
            raise CheckError("default route table changed during read-only test")
        report = {
            "result": "PASS",
            "persistent_network_state_changed": False,
            "transient_reconnect_exercised": reconnect_attempted,
            "band": args.band,
            "frequency_mhz": wifi["frequency_mhz"],
            "associated": True,
            "security": security,
            "gateway_ping": ping,
            "dns_a_answers": answer_count,
            "reconnect_test": "PASS" if args.exercise_reconnect else "NOT_RUN",
            "throughput_mbps": throughput_mbps,
            "station_counters_before": counters_before,
            "station_counters_after": counters_after,
            "default_route_unchanged": True,
            "identifiers_and_addresses_redacted": True,
        }
        print(json.dumps(report, sort_keys=True))
        return 0
    except CheckError as exc:
        print(json.dumps({"result": "FAIL", "reason": str(exc),
                          "persistent_network_state_changed": False,
                          "transient_reconnect_requested": reconnect_attempted}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
