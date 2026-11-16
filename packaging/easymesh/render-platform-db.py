#!/usr/bin/env python3
"""Render private prplMesh interface mappings without printing credentials."""
from __future__ import annotations

import argparse
import configparser
import os
from pathlib import Path
import re
import sys

IFNAME_RE = re.compile(r"^[A-Za-z0-9_.-]{1,15}$")


def names(config: configparser.ConfigParser, key: str) -> list[str]:
    values = [value.strip() for value in config.get("node", key, fallback="").split(",") if value.strip()]
    if len(values) != 2 or any(not IFNAME_RE.fullmatch(value) for value in values):
        raise ValueError(f"{key} must contain exactly two valid interface names")
    if len(set(values)) != 2:
        raise ValueError(f"{key} contains duplicates")
    return values


def render_text(template: str, node_text: str) -> str:
    config = configparser.ConfigParser(interpolation=None, strict=True)
    config.read_string(node_text)
    radios = names(config, "radio_ifaces")
    stations = names(config, "station_ifaces")
    # Additional radio indices are optional. They are needed by some upstream
    # Agent builds even when wired 1905 is the only feature under test.
    extra_raw = config.get("node", "radio_ifaces_extra", fallback="").strip()
    extra = []
    if extra_raw:
        extra = [value.strip() for value in extra_raw.split(",")]
        if (len(extra) != 2 or any(not IFNAME_RE.fullmatch(value) for value in extra)):
            raise ValueError("radio_ifaces_extra must contain exactly two valid interface names")
    if len(set(radios + stations + extra)) != len(radios + stations + extra):
        raise ValueError("radio/station/extra interface names must be distinct")
    for i in range(2):
        template = template.replace(f"@RADIO{i}@", radios[i]).replace(f"@STA{i}@", stations[i])
    if "@RADIO" in template or "@STA" in template or "REPLACE_WITH" in template:
        raise ValueError("private platform database still contains an unconfigured placeholder")
    if extra:
        if not template.endswith("\n"):
            template += "\n"
        for i, iface in enumerate(extra, start=2):
            template += f"wireless_interface_{i}={iface}\n"
    return template


def check_private(path: Path) -> None:
    st = path.lstat()
    if path.is_symlink() or not path.is_file() or st.st_uid != 0 or st.st_mode & 0o077:
        raise ValueError(f"unsafe owner or mode: {path.name}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--template", type=Path, required=True)
    parser.add_argument("--node-conf", type=Path, default=Path("/etc/terminal6-easymesh/node.conf"))
    parser.add_argument("--output", type=Path, default=Path("/etc/terminal6-easymesh/prplmesh_platform_db"))
    args = parser.parse_args()
    try:
        if os.geteuid() != 0:
            raise ValueError("must run as root")
        check_private(args.template)
        check_private(args.node_conf)
        content = render_text(args.template.read_text(encoding="utf-8"), args.node_conf.read_text(encoding="utf-8"))
        fd = os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(content)
        os.chmod(args.output, 0o600)
    except (OSError, ValueError, configparser.Error) as exc:
        print(f"EASYMESH_DB_RENDER=FAIL reason={exc.__class__.__name__}", file=sys.stderr)
        return 1
    print("EASYMESH_DB_RENDER=PASS mode=0600 secrets=redacted")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
