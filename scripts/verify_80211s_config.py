#!/usr/bin/env python3
"""Fail-closed checks for the Linux/mac80211/mt7996 802.11s build inputs."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


def parse_config(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8", errors="strict").splitlines():
        match = re.fullmatch(r"CONFIG_([A-Za-z0-9_]+)=(.*)", line)
        if match:
            values[match.group(1)] = match.group(2)
        else:
            match = re.fullmatch(r"# CONFIG_([A-Za-z0-9_]+) is not set", line)
            if match:
                values[match.group(1)] = "n"
    return values


def verify(config: Path, source: Path) -> dict[str, object]:
    values = parse_config(config)
    required = {
        "CFG80211": {"y"},
        "MAC80211": {"y"},
        "MAC80211_MESH": {"y"},
        "MT7996E": {"m", "y"},
    }
    missing = {
        name: values.get(name, "<unset>")
        for name, accepted in required.items()
        if values.get(name) not in accepted
    }
    checks = {
        "mac80211_mesh_kconfig": source / "net/mac80211/Kconfig",
        "mesh_core": source / "net/mac80211/mesh.c",
        "mesh_hwmp": source / "net/mac80211/mesh_hwmp.c",
        "mesh_peering": source / "net/mac80211/mesh_plink.c",
        "mesh_path_table": source / "net/mac80211/mesh_pathtbl.c",
        "mt7996_mesh_advertisement": source / "drivers/net/wireless/mediatek/mt76/mt7996/init.c",
        "mt7996_mesh_vif": source / "drivers/net/wireless/mediatek/mt76/mt7996/main.c",
        "mt7996_mesh_mcu": source / "drivers/net/wireless/mediatek/mt76/mt7996/mcu.c",
        "mt7996_mesh_rx": source / "drivers/net/wireless/mediatek/mt76/mt7996/mac.c",
    }
    source_missing = [name for name, path in checks.items() if not path.is_file()]
    source_markers = {
        "mac80211_mesh_kconfig": ("config MAC80211_MESH",),
        "mesh_core": ("ieee80211s_init",),
        "mesh_hwmp": ("mesh_path_start_discovery", "MPATH_PREQ"),
        "mesh_peering": ("NL80211_PLINK_ESTAB",),
        "mesh_path_table": ("mesh_path_lookup",),
        "mt7996_mesh_advertisement": ("CONFIG_MAC80211_MESH", "NL80211_IFTYPE_MESH_POINT"),
        "mt7996_mesh_vif": ("NL80211_IFTYPE_MESH_POINT",),
        "mt7996_mesh_mcu": ("NL80211_IFTYPE_MESH_POINT",),
        "mt7996_mesh_rx": ("ieee80211_has_a4", "is_mesh"),
    }
    source_failures: list[str] = []
    for name, path in checks.items():
        if not path.is_file():
            continue
        content = path.read_text(encoding="utf-8", errors="replace")
        for marker in source_markers[name]:
            if marker not in content:
                source_failures.append(f"{name}:{marker}")
    return {
        "schema": 1,
        "config": str(config),
        "source": str(source),
        "required_config": {name: values.get(name, "<unset>") for name in required},
        "config_failures": missing,
        "source_missing": source_missing,
        "source_failures": source_failures,
        "pass": not missing and not source_missing and not source_failures,
        "scope": "build-input check only; no hardware/runtime mesh behavior is proven",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--source", required=True, type=Path)
    args = parser.parse_args()
    report = verify(args.config, args.source)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
