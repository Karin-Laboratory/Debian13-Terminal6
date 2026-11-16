#!/usr/bin/env python3
"""Offline, privacy-preserving acceptance of 802.11be two-link evidence.

This validator never connects to hardware or starts RF.  Its verdict validates
consistency of supplied evidence, not the authenticity of the observations.
"""

import argparse
import json
from pathlib import Path


PASS = "PASS"
HWSIM_PASS = "HWSIM_PASS"
NOT_PROVEN = "NOT_PROVEN"


def _valid_ids(value, number):
    return (isinstance(value, list) and len(value) == number
            and all(type(v) is int and 0 <= v <= 15 for v in value)
            and len(set(value)) == number)


def _valid_count(value):
    return type(value) is int and value >= 0


def _valid_frequency(value, low, high):
    return type(value) is int and low <= value <= high and value % 5 == 0


def _check_transitions(transitions, ids, reasons):
    """Require observable down/up cycles for both links and final reconnect."""
    if not isinstance(transitions, list) or len(transitions) != 5:
        reasons.append("two down/up cycles and one reconnect required")
        return
    active = set(ids)
    failed = None
    completed = set()
    for idx, item in enumerate(transitions):
        if not isinstance(item, dict):
            reasons.append("invalid transition record")
            return
        event = item.get("event")
        link = item.get("link_id")
        if event != "reconnect" and (type(link) is not int or link not in ids):
            reasons.append("transition link ID is not an established MLD link")
            return
        if event == "link_down":
            if failed is not None or link not in active or link in completed:
                reasons.append("invalid link-down state transition")
                return
            failed = link
            active.remove(link)
        elif event == "link_up":
            if failed is None or link != failed:
                reasons.append("invalid link-up state transition")
                return
            active.add(link)
            completed.add(link)
            failed = None
        elif event == "reconnect":
            if idx != len(transitions) - 1 or link is not None or failed is not None or completed != set(ids):
                reasons.append("reconnect does not follow both completed recoveries")
                return
        else:
            reasons.append("unknown transition event")
            return
        reported = item.get("active_link_ids")
        if not _valid_ids(reported, len(active)) or set(reported) != active:
            reasons.append("transition active links contradict state")
        if item.get("ip_bidirectional_pass") is not True:
            reasons.append("IP continuity/reconnection unproven")
    if completed != set(ids) or failed is not None:
        reasons.append("both link recoveries unproven")


def evaluate(record):
    """Return a conservative verdict for schema v2 hardware or hwsim evidence."""
    reasons = []
    if not isinstance(record, dict):
        return {"mlo_two_link_ip": NOT_PROVEN, "reasons": ["evidence must be an object"]}

    if type(record.get("schema_version")) is not int or record["schema_version"] != 2:
        reasons.append("schema_version 2 required; legacy boolean-only evidence is insufficient")
    environment = record.get("environment")
    if environment not in ("hardware", "hwsim"):
        reasons.append("environment must be hardware or hwsim")
    if record.get("same_mld_peer") is not True:
        reasons.append("same MLD peer unproven")
    if record.get("sta_mlo_capable") is not True:
        reasons.append("MLO-capable STA unproven")
    if record.get("ip_bidirectional_pass") is not True:
        reasons.append("bidirectional IP unproven")
    if environment == "hardware" and record.get("six_ghz_authorization_verified") is not True:
        reasons.append("6 GHz authorization gate unverified")

    links = record.get("links")
    if not isinstance(links, list) or len(links) != 2 or not all(isinstance(l, dict) for l in links):
        reasons.append("exactly two link objects required")
        links = []
    ids = [link.get("link_id") for link in links]
    valid_ids = _valid_ids(ids, 2)
    if not valid_ids:
        reasons.append("two distinct valid link IDs unproven")
    bands = []
    radios = []
    for link in links:
        band = link.get("band")
        bands.append(band)
        if band not in ("5GHz", "6GHz"):
            reasons.append("expected 5GHz/6GHz band")
        if type(link.get("width_mhz")) is not int or link.get("width_mhz") != 160:
            reasons.append("each MLO link must use exactly 160 MHz; 320 MHz prohibited")
        radio_id = link.get("radio_id")
        if type(radio_id) is not int or radio_id < 0:
            reasons.append("per-link radio_id unavailable")
        else:
            radios.append(radio_id)
        if link.get("active") is not True or link.get("associated") is not True:
            reasons.append("link is not active and associated")
        bounds = (5000, 5895) if band == "5GHz" else (5925, 7125)
        primary = link.get("primary_freq_mhz")
        center = link.get("center_freq_mhz")
        if not (_valid_frequency(primary, *bounds) and _valid_frequency(center, *bounds)
                and abs(primary - center) < 80):
            reasons.append("primary/center frequency for 160 MHz link missing or inconsistent")
        for direction in ("tx", "rx"):
            before = link.get(direction + "_before")
            after = link.get(direction + "_after")
            if not _valid_count(before) or not _valid_count(after) or after <= before:
                reasons.append(f"link {link.get('link_id')} {direction} did not advance")
    if len(bands) != 2 or not all(isinstance(b, str) for b in bands) or set(bands) != {"5GHz", "6GHz"}:
        reasons.append("5GHz and 6GHz link assignment unproven")
    if len(radios) != 2 or radios[0] == radios[1]:
        reasons.append("two distinct radio IDs not evidenced; PCI endpoints are not radios")

    for role in ("ap_mld", "sta_mld"):
        state = record.get(role)
        if not isinstance(state, dict):
            reasons.append(f"{role} association evidence missing")
            continue
        if state.get("associated") is not True:
            reasons.append(f"{role} association unproven")
        active = state.get("active_link_ids")
        if not valid_ids or not _valid_ids(active, 2) or set(active) != set(ids):
            reasons.append(f"{role} active link IDs inconsistent")
        tag = state.get("association_tag")
        if not isinstance(tag, str) or not tag or len(tag) > 64:
            reasons.append(f"{role} sanitized association tag missing")
    ap = record.get("ap_mld")
    sta = record.get("sta_mld")
    if (isinstance(ap, dict) and isinstance(sta, dict)
            and ap.get("association_tag") != sta.get("association_tag")):
        reasons.append("AP and STA refer to different MLD associations")

    if valid_ids:
        _check_transitions(record.get("transitions"), ids, reasons)
    else:
        reasons.append("link transitions cannot be checked without valid IDs")

    verdict = (NOT_PROVEN if reasons else (PASS if environment == "hardware" else HWSIM_PASS))
    return {"mlo_two_link_ip": verdict, "reasons": sorted(set(reasons))}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("evidence", type=Path)
    args = parser.parse_args()
    try:
        result = evaluate(json.loads(args.evidence.read_text(encoding="utf-8")))
    except (OSError, ValueError) as exc:
        result = {"mlo_two_link_ip": NOT_PROVEN, "reasons": [f"invalid evidence file: {exc}"]}
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result["mlo_two_link_ip"] in (PASS, HWSIM_PASS) else 1


if __name__ == "__main__":
    raise SystemExit(main())