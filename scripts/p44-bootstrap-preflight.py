#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Read-only P44 onboarding preflight; not a firewall or proof of cable isolation."""

import argparse
import json
import subprocess
import sys

PORTS = {"lan2", "lan3"}
BRIDGE = "br-lan"
LOCAL = "192.168.1.1"
PEER = "192.168.1.50"


def require(ok, message):
    if not ok:
        raise ValueError(message)


def verify_topology(port, links, addrs, routes):
    require(port in PORTS, "Select one of the physical LAN ports.")
    by_name = {x["ifname"]: x for x in links}
    require(len(by_name) == len(links), "Ambiguous kernel interface list.")
    bridge = by_name.get(BRIDGE, {})
    require(bridge.get("linkinfo", {}).get("info_kind") == "bridge",
            "Expected the Debian management bridge.")
    members = {x["ifname"] for x in links if x.get("master") == BRIDGE}
    require(members == PORTS, "Unexpected management bridge membership.")
    for member in PORTS:
        flags = set(by_name[member].get("flags", ()))
        require("UP" in flags, "Both LAN interfaces must be observable and enabled.")
        require(("LOWER_UP" in flags) == (member == port),
                "Expected carrier only on the selected direct-cable port.")
    local_owners = [
        (row["ifname"], addr["prefixlen"])
        for row in addrs for addr in row.get("addr_info", ())
        if addr.get("family") == "inet" and addr.get("local") == LOCAL
    ]
    require(local_owners == [(BRIDGE, 24)], "Unexpected owner of the management address.")
    require(len(routes) == 1, "Ambiguous route to the onboarding peer.")
    route = routes[0]
    require(route.get("dev") == BRIDGE and not route.get("gateway")
            and route.get("prefsrc", route.get("src")) == LOCAL,
            "Onboarding peer must use the direct management bridge route.")
    require(route.get("type", "unicast") == "unicast", "Unexpected route type.")


def ip_json(*args):
    result = subprocess.run(["/usr/sbin/ip", "-j", *args], check=True,
                            timeout=5, capture_output=True, text=True)
    return json.loads(result.stdout)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("port", choices=sorted(PORTS))
    args = parser.parse_args()
    try:
        verify_topology(args.port, ip_json("-d", "link", "show"),
                        ip_json("-4", "addr", "show"),
                        ip_json("-4", "route", "get", PEER))
    except (KeyError, TypeError, ValueError, OSError, subprocess.SubprocessError) as exc:
        print(f"Onboarding preflight refused: {exc}", file=sys.stderr)
        return 1
    print("P44_BOOTSTRAP_TOPOLOGY_PREFLIGHT_PASS (assert direct cable and verify ingress filter separately)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
