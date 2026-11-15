#!/usr/bin/env python3
"""Read-only preflight for a separately provisioned prplMesh Linux node."""
from __future__ import annotations

import argparse
import configparser
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys

IFNAME_RE = re.compile(r"^[A-Za-z0-9_.-]{1,15}$")
ROLES = {"controller", "agent", "controller-agent"}
MODE = {
    "controller": "Multi-AP-Controller",
    "agent": "Multi-AP-Agent",
    "controller-agent": "Multi-AP-Controller-and-Agent",
}


class PreflightError(Exception):
    pass


def split_names(value: str) -> list[str]:
    names = [item.strip() for item in value.split(",") if item.strip()]
    if any(not IFNAME_RE.fullmatch(item) for item in names):
        raise PreflightError("invalid interface name in node.conf")
    if len(names) != len(set(names)):
        raise PreflightError("duplicate interface in node.conf")
    return names


def load_config(path: Path) -> dict[str, str]:
    parser = configparser.ConfigParser(interpolation=None, strict=True)
    try:
        with path.open(encoding="utf-8") as stream:
            parser.read_file(stream)
    except (OSError, configparser.Error) as exc:
        raise PreflightError(f"cannot read node configuration: {exc.__class__.__name__}") from None
    if not parser.has_section("node"):
        raise PreflightError("missing [node] section")
    return dict(parser.items("node"))


def read_addresses(iface: str) -> list[dict]:
    try:
        result = subprocess.run(
            ["ip", "-json", "-4", "address", "show", "dev", iface],
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired):
        return []
    if result.returncode:
        return []
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return []


def has_global_ipv4(iface: str) -> bool:
    for device in read_addresses(iface):
        for entry in device.get("addr_info", []):
            if entry.get("family") == "inet" and entry.get("scope") == "global":
                return True
    return False


def is_unix_socket(path: Path) -> bool:
    try:
        return stat.S_ISSOCK(path.lstat().st_mode)
    except OSError:
        return False


def validate(config: dict[str, str], sysfs: Path, socket_root: Path, address_probe=has_global_ipv4) -> None:
    role = config.get("role", "")
    if role not in ROLES:
        raise PreflightError("role must be controller, agent, or controller-agent")

    management = split_names(config.get("management_ifaces", ""))
    wired_backhaul = split_names(config.get("wired_backhaul_ifaces", ""))
    stations = split_names(config.get("station_ifaces", ""))
    radios = split_names(config.get("radio_ifaces", ""))
    if not management:
        raise PreflightError("management_ifaces are required")
    if not radios:
        raise PreflightError("radio_ifaces is required")
    if not stations:
        raise PreflightError("station_ifaces is required for prplMesh backhaul control")
    if len(radios) != 2:
        raise PreflightError("this prplMesh Linux BPL build supports exactly two configured radios")
    groups = (management, wired_backhaul, radios, stations)
    if any(set(left) & set(right) for index, left in enumerate(groups) for right in groups[index + 1:]):
        raise PreflightError("management/wired-backhaul/AP-radio/STA interfaces must be disjoint")

    all_ifaces = management + wired_backhaul + radios + stations
    for iface in all_ifaces:
        if not (sysfs / "class/net" / iface).exists():
            raise PreflightError(f"configured interface is absent: {iface}")
    for iface in management:
        if not address_probe(iface):
            raise PreflightError(f"management IPv4 is not configured: {iface}")
    for iface in radios:
        if not (sysfs / "class/net" / iface / "phy80211").exists():
            raise PreflightError(f"configured radio interface is not a Wi-Fi netdev: {iface}")
        if not is_unix_socket(socket_root / "hostapd" / iface):
            raise PreflightError(f"hostapd control socket is absent: {iface}")
    for iface in stations:
        if not (sysfs / "class/net" / iface / "phy80211").exists():
            raise PreflightError(f"configured station interface is not a Wi-Fi netdev: {iface}")


def validate_private_files(config_path: Path, db_path: Path, enabled_path: Path) -> None:
    if os.geteuid() != 0:
        raise PreflightError("startup preflight must run as root")
    for path, max_mode in ((config_path, 0o022), (db_path, 0o077), (enabled_path, 0o077)):
        try:
            info = path.lstat()
        except OSError:
            raise PreflightError(f"required startup file is absent: {path.name}") from None
        if path.is_symlink() or not path.is_file() or info.st_uid != 0 or info.st_mode & max_mode:
            raise PreflightError(f"unsafe owner or permissions: {path.name}")


def validate_platform_db(path: Path, config: dict[str, str], socket_root: Path = Path("/run")) -> None:
    values: dict[str, str] = {}
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.split("#", 1)[0].strip()
            if not line or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key, value = key.strip(), value.strip()
            if key in values:
                raise PreflightError("duplicate key in prplMesh platform database")
            values[key] = value
    except OSError as exc:
        raise PreflightError(f"cannot read platform database: {exc.__class__.__name__}") from None
    expected_mode = MODE.get(config.get("role", ""))
    if values.get("management_mode") != expected_mode:
        raise PreflightError("platform database management_mode does not match node role")
    backhaul_wire = values.get("backhaul_wire_iface", "")
    if backhaul_wire and backhaul_wire not in split_names(config.get("wired_backhaul_ifaces", "")):
        raise PreflightError("platform database backhaul interface is not dedicated")
    radios = split_names(config.get("radio_ifaces", ""))
    if len(radios) != 2:
        raise PreflightError("this prplMesh Linux BPL build supports exactly two configured radios")
    for index, iface in enumerate(radios):
        if values.get(f"wireless_interface_{index}") != iface:
            raise PreflightError(f"platform DB radio {index} mapping differs from node.conf")
        fields = {name: values.get(f"wireless.{iface}.{name}", "") for name in ("ssid", "security_mode", "psk")}
        if any(not value or "REPLACE_WITH" in value for value in fields.values()):
            raise PreflightError(f"private wireless credentials are incomplete: {iface}")
        if "#" in fields["ssid"] or not 1 <= len(fields["ssid"].encode("utf-8")) <= 32:
            raise PreflightError(f"SSID is invalid for platform database parsing: {iface}")
        if fields["security_mode"] not in {"wpa2", "wpa2-psk", "wpa3-sae", "wpa2-wpa3-transition"}:
            raise PreflightError("unsupported wireless security mode")
        psk = fields["psk"]
        valid_passphrase = psk.isascii() and 8 <= len(psk) <= 63 and all(0x20 <= ord(c) <= 0x7e for c in psk)
        valid_hex_psk = len(psk) == 64 and all(c in "0123456789abcdefABCDEF" for c in psk)
        if "#" in psk or not (valid_passphrase or valid_hex_psk):
            raise PreflightError(f"wireless PSK has invalid WPA passphrase/PSK length: {iface}")
        hostap_path = values.get(f"hostapd_ctrl_path_{iface}", "")
        hostap_prefix = "/run/hostapd/"
        if not hostap_path.startswith(hostap_prefix):
            raise PreflightError(f"invalid hostapd control path for {iface}")
        hostap_leaf = hostap_path[len(hostap_prefix):]
        if not IFNAME_RE.fullmatch(hostap_leaf) or not (socket_root / "hostapd" / hostap_leaf).exists():
            raise PreflightError(f"hostapd control socket is absent for {iface}")

        station_path = values.get(f"wpa_supplicant_ctrl_path_{iface}", "")
        station_prefix = "/run/wpa_supplicant/"
        if not station_path.startswith(station_prefix):
            raise PreflightError(f"invalid wpa_supplicant control path for {iface}")
        station_leaf = station_path[len(station_prefix):]
        if (not IFNAME_RE.fullmatch(station_leaf)
                or station_leaf not in split_names(config.get("station_ifaces", ""))
                or not is_unix_socket(socket_root / "wpa_supplicant" / station_leaf)):
            raise PreflightError(f"wpa_supplicant station control socket is absent for {iface}")


def main() -> int:
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--config", type=Path, default=Path("/etc/terminal6-easymesh/node.conf"))
    cli.add_argument("--sysfs", type=Path, default=Path("/sys"))
    cli.add_argument("--run", type=Path, default=Path("/run"))
    cli.add_argument("--platform-db", type=Path, default=Path("/etc/terminal6-easymesh/prplmesh_platform_db"))
    cli.add_argument("--enabled-marker", type=Path, default=Path("/etc/terminal6-easymesh/enabled"))
    cli.add_argument("--for-start", action="store_true", help="enforce root-only live-start gates")
    args = cli.parse_args()
    try:
        config = load_config(args.config)
        validate(config, args.sysfs, args.run)
        if args.for_start:
            validate_private_files(args.config, args.platform_db, args.enabled_marker)
            validate_platform_db(args.platform_db, config, args.run)
    except PreflightError as exc:
        print(f"EASYMESH_PREFLIGHT=FAIL reason={exc}", file=sys.stderr)
        return 1
    print("EASYMESH_PREFLIGHT=PASS read_only=true")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
