#!/usr/bin/env python3
"""Evaluate sanitized MLD measurements; never configures a radio.

Input JSON is collected before/after one IP test.  Counters must belong to
one associated MLD peer, not two unrelated station interfaces.
"""

import argparse
import json
from pathlib import Path


def evaluate(record):
    reasons = []
    if record.get("same_mld_peer") is not True:
        reasons.append("same MLD peer unproven")
    if record.get("sta_mlo_capable") is not True:
        reasons.append("MLO-capable STA unproven")
    if record.get("ip_bidirectional_pass") is not True:
        reasons.append("bidirectional IP unproven")
    links = record.get("links", [])
    if not isinstance(links, list) or len(links) != 2:
        reasons.append("exactly two links required")
        links = []
    ids = [link.get("link_id") for link in links if isinstance(link, dict)]
    if len(ids) != 2 or any(type(i) is not int or not 0 <= i <= 15 for i in ids) or len(set(ids)) != 2:
        reasons.append("two distinct valid link IDs unproven")
    bands = set()
    for link in links:
        if not isinstance(link, dict):
            reasons.append("invalid link record")
            continue
        band = link.get("band")
        bands.add(band)
        if band not in ("5GHz", "6GHz") or link.get("width_mhz") != 160:
            reasons.append("5/6 GHz 160 MHz width unproven")
        for direction in ("tx", "rx"):
            before = link.get(direction + "_before")
            after = link.get(direction + "_after")
            if type(before) is not int or type(after) is not int or before < 0 or after <= before:
                reasons.append(f"link {link.get('link_id')} {direction} did not advance")
    if bands != {"5GHz", "6GHz"}:
        reasons.append("5 and 6 GHz radio assignment unproven")
    if record.get("six_ghz_authorization_verified") is not True:
        reasons.append("6 GHz authorization gate unverified")
    return {"mlo_two_link_ip": "PASS" if not reasons else "NOT_PROVEN",
            "reasons": sorted(set(reasons))}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("evidence", type=Path)
    args = parser.parse_args()
    result = evaluate(json.loads(args.evidence.read_text()))
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result["mlo_two_link_ip"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
