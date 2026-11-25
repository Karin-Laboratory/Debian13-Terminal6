# SPDX-License-Identifier: MIT
"""Offline link observation classifier; no device access or startup actions."""

import argparse
import json

# Candidate full-duplex rates for the external jack test matrix; a reported
# link is not a datapath result, and no caller should gate initialization on it.
EXTERNAL_RATES = (100, 1000)


def observe(cpu_carrier, cpu_speed, cpu_duplex,
            jack_carrier, jack_speed, jack_duplex):
    if cpu_carrier != 1:
        cpu = "no-carrier" if cpu_carrier == 0 else "unknown-carrier"
    elif (cpu_speed, cpu_duplex) != (2500, "full"):
        cpu = "unexpected-fixed-link"
    else:
        cpu = "fixed-link-observed"

    if jack_carrier != 1:
        jack = "no-carrier" if jack_carrier == 0 else "unknown-carrier"
    elif jack_speed not in EXTERNAL_RATES or jack_duplex != "full":
        jack = "outside-test-matrix"
    else:
        jack = "negotiated-link-observed"

    return {"cpu_link": cpu, "external_link": jack,
            "external_speed_mbps": jack_speed, "datapath": "not-tested"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for prefix in ("cpu", "jack"):
        parser.add_argument(f"--{prefix}-carrier", type=int, required=True)
        parser.add_argument(f"--{prefix}-speed", type=int, required=True)
        parser.add_argument(f"--{prefix}-duplex", required=True)
    args = parser.parse_args()
    print(json.dumps(observe(**vars(args)), sort_keys=True))


if __name__ == "__main__":
    main()
