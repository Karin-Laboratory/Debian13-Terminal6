#!/usr/bin/env python3
"""Read-only C-unit SSH probe through the EXISTING raspi4 management key.

No credential creation, no host key changes, no remote config write or RF.
Any private remote output is saved locally mode 0600, not printed.
"""
from __future__ import annotations

import argparse
import ipaddress
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys

HOST_RE = re.compile(r"^[A-Za-z0-9_.@-]{1,128}$")
KNOWN_COMMANDS = (
    "uname -r",
    "cat /proc/cmdline",
    "test -e /proc/config.gz && zcat /proc/config.gz | grep -E "
    "'CONFIG_MAC80211_MESH|CONFIG_CFG80211_REQUIRE_SIGNED_REGDB' || :",
    "ip route show default",
    "iw dev 2>/dev/null || :",
    "iw phy 2>/dev/null || :",
    "iw reg get 2>/dev/null || :",
)


def classify_failure(stderr: str, status: int) -> str:
    low = stderr.lower()
    if "permission denied (publickey)" in low or "no more authentication methods" in low:
        return "TARGET_PUBLICKEY_REJECTED"
    if "host key verification failed" in low or "host key is not known" in low:
        return "KNOWN_HOSTS_MISMATCH_OR_MISSING"
    if "identity file" in low or "no such file" in low:
        return "EXISTING_IDENTITY_UNAVAILABLE"
    if "connection refused" in low:
        return "TARGET_SSH_NOT_LISTENING"
    if "timed out" in low or status == 124:
        return "CONNECTIVITY_TIMEOUT"
    return "UNKNOWN_SSH_FAILURE"


def validate(gateway: str, target: str, identity_on_gateway: str) -> None:
    if not HOST_RE.fullmatch(gateway) or gateway.startswith("-"):
        raise ValueError("invalid explicit raspi4 gateway")
    if not target.startswith("root@"):
        raise ValueError("C-unit target must be an explicit root@IPv4")
    ipaddress.IPv4Address(target[5:])
    if (not identity_on_gateway.startswith("/") or
            not re.fullmatch(r"/[A-Za-z0-9_./-]{1,256}", identity_on_gateway) or
            ".." in Path(identity_on_gateway).parts):
        raise ValueError("existing gateway-side identity must use a safe absolute path")


def ssh_options() -> list[str]:
    return ["-o", "BatchMode=yes",
            "-o", "IdentitiesOnly=yes",
            "-o", "StrictHostKeyChecking=yes",
            "-o", "UpdateHostKeys=no",
            "-o", "ForwardAgent=no",
            "-o", "ConnectTimeout=7"]


def make_remote_probe(target: str, identity: str) -> str:
    readonly = " ; ".join(KNOWN_COMMANDS)
    # Both the raspi4-side shell and the target shell need separate quoting.
    # Preserve the complete readonly script as one target command.
    args = ["ssh", *ssh_options(), "-i", identity, target,
            "sh -c " + shlex.quote(readonly)]
    return shlex.join(args)


def execute(gateway: str, target: str, identity: str, output: Path) -> dict:
    validate(gateway, target, identity)
    if output.exists() or output.is_symlink():
        raise ValueError("choose a new private output directory")
    output.mkdir(mode=0o700, parents=True)
    output.chmod(0o700)
    precheck = ["ssh", *ssh_options(), gateway, "printf CUNIT_GATEWAY_READY"]
    try:
        first = subprocess.run(precheck, capture_output=True, text=True, timeout=20)
    except (OSError, subprocess.TimeoutExpired):
        return {"gateway_ssh": "BLOCKED", "target_ssh": "NOT_TESTED",
                "reason": "GATEWAY_UNAVAILABLE"}
    if first.returncode or "CUNIT_GATEWAY_READY" not in first.stdout:
        return {"gateway_ssh": "BLOCKED", "target_ssh": "NOT_TESTED",
                "reason": classify_failure(first.stderr, first.returncode)}
    cmd = ["ssh", *ssh_options(), gateway, make_remote_probe(target, identity)]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=55)
    except (OSError, subprocess.TimeoutExpired):
        return {"gateway_ssh": "PASS", "target_ssh": "BLOCKED",
                "reason": "TARGET_TIMEOUT_OR_TOOL_FAILURE"}
    log = output / "cunit-readonly-private.log"
    fd = os.open(log, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as stream:
        stream.write(result.stdout + "\n" + result.stderr)
    if result.returncode:
        return {"gateway_ssh": "PASS", "target_ssh": "FAIL",
                "reason": classify_failure(result.stderr, result.returncode),
                "private_log_created": True}
    return {"gateway_ssh": "PASS", "target_ssh": "PASS",
            "readonly_inventory": "COLLECTED",
            "private_log_created": True}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gateway", required=True, help="preexisting raspi4 SSH alias/user@host")
    parser.add_argument("--target", required=True, help="explicit root@IPv4 on C management LAN")
    parser.add_argument("--existing-target-identity-on-gateway", required=True)
    parser.add_argument("--private-output", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = execute(args.gateway, args.target,
                         args.existing_target_identity_on_gateway, args.private_output)
    except (OSError, ValueError) as exc:
        result = {"gateway_ssh": "BLOCKED", "target_ssh": "NOT_TESTED",
                  "reason": exc.__class__.__name__}
    print(json.dumps(result, sort_keys=True))
    return 0 if result.get("target_ssh") == "PASS" else 2


if __name__ == "__main__":
    sys.exit(main())
