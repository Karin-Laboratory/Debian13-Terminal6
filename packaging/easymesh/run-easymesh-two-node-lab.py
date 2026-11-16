#!/usr/bin/env python3
"""Opt-in two-container IEEE1905 lab: no changes to A/C, Wi-Fi, or host management IF."""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import shlex
from pathlib import Path
import secrets
import shutil
import signal
import subprocess
import sys
import time

IMAGE_CHARS = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._/:-@")


class LabError(RuntimeError):
    pass


def command(argv: list[str], *, timeout: float = 30) -> str:
    try:
        result = subprocess.run(argv, capture_output=True, text=True, timeout=timeout, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise LabError(f"laboratory command unavailable: {argv[0]} ({exc.__class__.__name__})") from None
    if result.returncode:
        # Do not echo Docker stderr: it can contain private registry details.
        raise LabError(f"laboratory command failed: {argv[0]} exit={result.returncode}")
    return result.stdout.strip()


def validate_image(image: str) -> str:
    if not image or image.startswith("-") or len(image) > 200 or any(c not in IMAGE_CHARS for c in image):
        raise LabError("invalid prebuilt Docker image reference")
    return image


def plan_images(controller_image: str, agent_image: str) -> list[list[str]]:
    return [["docker", "image", "inspect", validate_image(image)]
            for image in (controller_image, agent_image)]


def run_container(name: str, network: str, image: str, startup: str) -> str:
    return command([
        "docker", "run", "--detach", "--rm", "--name", name,
        "--network", network, "--cap-add=NET_RAW", "--cap-add=NET_ADMIN",
        "--security-opt=no-new-privileges", "--pull=never", image, startup,
    ])


def capture(bridge: str, path: Path, duration: int, *, during_capture=None):
    """Start capture before starting/restarting nodes; only on our dedicated bridge."""
    with path.open("wb") as output:
        proc = subprocess.Popen([
            "tcpdump", "-i", bridge, "-n", "-s", "65535", "-U", "-w", "-",
            "ether", "proto", "0x893a",
        ], stdout=output, stderr=subprocess.DEVNULL)
        try:
            if proc.poll() is not None:
                raise LabError("tcpdump could not start; no capture accepted")
            time.sleep(0.4)
            if proc.poll() is not None:
                raise LabError("tcpdump stopped before network action")
            if during_capture is not None:
                during_capture()
            time.sleep(duration)
        finally:
            if proc.poll() is None:
                proc.send_signal(signal.SIGINT)
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=5)
        if proc.returncode not in (0, 130):
            raise LabError("tcpdump did not shut down cleanly")
    if path.stat().st_size < 24:
        raise LabError("no valid capture generated")


def load_verifier():
    path = Path(__file__).with_name("verify-ieee1905-pcap.py")
    spec = importlib.util.spec_from_file_location("lab_ieee1905_verifier", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def assess_capture(path: Path, ctrl_al: bytes, agent_al: bytes) -> dict:
    validator = load_verifier()
    if path.stat().st_size > validator.MAX_CAPTURE_SIZE:
        raise LabError("capture exceeds maximum parser size")
    return validator.inspect_pcap(path.read_bytes(), ctrl_al, agent_al)


def container_running(name: str) -> bool:
    return command(["docker", "inspect", "--format", "{{.State.Running}}", name]) == "true"


def wait_for_processes(container: str, expected: tuple[str, ...], *, seconds: float = 10) -> bool:
    """Assert actual prplMesh processes exist, not merely a running container."""
    end = time.monotonic() + seconds
    while True:
        try:
            listing = command(["docker", "top", container, "-eo", "args"])
            lines = listing.splitlines()[1:]
            found = all(any(re.search(r"(?:^|[/\s])" + re.escape(name) + r"(?:\s|$)", line)
                            for line in lines) for name in expected)
            if found:
                return True
        except LabError:
            pass
        if time.monotonic() >= end:
            return False
        time.sleep(0.5)


def agent_in_controller_db(controller: str, cli_args: str, agent_al: bytes) -> bool:
    """Check a fresh controller query, never report the raw topology or MAC."""
    argv = shlex.split(cli_args)
    if not argv or argv[0].startswith("-"):
        raise LabError("invalid controller DB query command")
    snapshot = command(["docker", "exec", controller, *argv], timeout=20)
    captured = re.findall(r"(?i)\b(?:[0-9a-f]{2}[:-]){5}[0-9a-f]{2}\b", snapshot)
    return agent_al in [bytes.fromhex(mac.replace(":", "").replace("-", "")) for mac in captured]


def lab(args) -> dict:
    if not args.execute:
        raise LabError("explicit --execute is required before creating lab resources")
    if not shutil.which("docker") or not shutil.which("tcpdump"):
        raise LabError("Docker and tcpdump are required on the designated lab host")
    verifier = load_verifier()
    ctrl_al = verifier.mac_bytes(args.controller_al)
    agent_al = verifier.mac_bytes(args.agent_al)
    if ctrl_al == agent_al or ctrl_al[0] & 1 or agent_al[0] & 1:
        raise LabError("two distinct unicast AL MACs are required")
    os.umask(0o077)
    if args.output.exists() or args.output.is_symlink():
        raise LabError("choose a new private output directory")
    args.output.mkdir(parents=True, mode=0o700)
    if not args.output.is_dir() or args.output.is_symlink():
        raise LabError("unsafe output directory")
    for probe in plan_images(args.controller_image, args.agent_image):
        command(probe)
    tag = secrets.token_hex(3)
    network, bridge = "t6mesh-" + tag, "t6m" + tag
    controller, agent = network + "-c", network + "-a"
    resources = {"network": False, "controller": False, "agent": False}
    result = {
        "environment": "dedicated-container-lab",
        "network_isolation": "docker-internal",
        "real_prplmesh_binary_confirmed": False,
        "controller_processes_running": False,
        "agent_processes_running": False,
        "controller_database_initial": False,
        "controller_database_after_agent_stop": None,
        "controller_database_after_agent_restart": False,
        "wire_topology_reestablished_after_restart": False,
        "controller_database_verified": False,
        "agent_loss_detection_verified": False,
        "node_recovery_verified": False,
        "baseline_wire_topology": False,
        "post_restart_wire_topology": False,
    }
    try:
        command(["docker", "network", "create", "--internal", "--driver", "bridge",
                 "--opt", f"com.docker.network.bridge.name={bridge}", network])
        resources["network"] = True

        def start_pair():
            run_container(controller, network, args.controller_image, "start-controller-agent")
            resources["controller"] = True
            run_container(agent, network, args.agent_image, "start-agent")
            resources["agent"] = True
            if not (container_running(controller) and container_running(agent)):
                raise LabError("at least one node stopped before initial capture")
            result["controller_processes_running"] = wait_for_processes(
                controller, ("ieee1905_transport", "beerocks_controller", "beerocks_agent"))
            result["agent_processes_running"] = wait_for_processes(
                agent, ("ieee1905_transport", "beerocks_agent"))
            if not (result["controller_processes_running"] and result["agent_processes_running"]):
                raise LabError("prplMesh processes not observed in both independent nodes")

        capture(bridge, args.output / "initial.ieee1905.pcap", args.duration,
                during_capture=start_pair)
        first = assess_capture(args.output / "initial.ieee1905.pcap", ctrl_al, agent_al)
        result["baseline_wire_topology"] = first["wire_topology_exchange"]
        result["baseline_message_types"] = first["message_type_counts"]
        if args.controller_db_command:
            result["controller_database_initial"] = agent_in_controller_db(
                controller, args.controller_db_command, agent_al)

        command(["docker", "stop", agent], timeout=25)
        resources["agent"] = False
        if not container_running(controller):
            raise LabError("controller exited during agent outage")
        capture(bridge, args.output / "agent-stopped.ieee1905.pcap", args.outage)
        if args.controller_db_command:
            result["controller_database_after_agent_stop"] = agent_in_controller_db(
                controller, args.controller_db_command, agent_al)

        def restart_agent():
            run_container(agent, network, args.agent_image, "start-agent")
            resources["agent"] = True
            if not container_running(agent) or not wait_for_processes(
                    agent, ("ieee1905_transport", "beerocks_agent")):
                raise LabError("agent process failed to restart")

        capture(bridge, args.output / "agent-restarted.ieee1905.pcap", args.duration,
                during_capture=restart_agent)
        resumed = assess_capture(args.output / "agent-restarted.ieee1905.pcap", ctrl_al, agent_al)
        result["post_restart_wire_topology"] = resumed["wire_topology_exchange"]
        result["post_restart_message_types"] = resumed["message_type_counts"]
        result["wire_topology_reestablished_after_restart"] = (
            result["baseline_wire_topology"] and result["post_restart_wire_topology"])
        if args.controller_db_command:
            result["controller_database_after_agent_restart"] = agent_in_controller_db(
                controller, args.controller_db_command, agent_al)
            result["controller_database_verified"] = (
                result["controller_database_initial"] and result["controller_database_after_agent_restart"])
            result["agent_loss_detection_verified"] = (
                result["controller_database_initial"] and
                result["controller_database_after_agent_stop"] is False)
            result["node_recovery_verified"] = (
                result["wire_topology_reestablished_after_restart"] and
                result["controller_database_verified"] and result["agent_loss_detection_verified"])
        # No DB command means DB and loss detection remain explicitly NOT VERIFIED.
        return result
    finally:
        for name, key in ((agent, "agent"), (controller, "controller")):
            if resources[key]:
                try:
                    command(["docker", "stop", name], timeout=25)
                except LabError:
                    pass
        if resources["network"]:
            try:
                command(["docker", "network", "rm", network], timeout=25)
            except LabError:
                pass


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--controller-image", required=True)
    ap.add_argument("--agent-image", required=True)
    ap.add_argument("--controller-al", required=True)
    ap.add_argument("--agent-al", required=True)
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--controller-db-command", help="optional in-container CLI command, e.g. beerocks_cli -c bml_conn_map")
    ap.add_argument("--duration", type=int, default=60)
    ap.add_argument("--outage", type=int, default=45)
    ap.add_argument("--execute", action="store_true", help="permit temporary Docker network/containers")
    args = ap.parse_args()
    try:
        if not (10 <= args.duration <= 300 and 10 <= args.outage <= 300):
            raise LabError("duration and outage must be 10..300 seconds")
        result = lab(args)
        print(json.dumps(result, sort_keys=True))
        (args.output / "verdict.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
        return 0 if result["node_recovery_verified"] else 1
    except (OSError, ValueError, LabError) as exc:
        print(f"EASYMESH_TWO_NODE_LAB=NOT_PROVEN reason={exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
