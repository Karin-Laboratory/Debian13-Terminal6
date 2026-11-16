#!/usr/bin/env python3
"""Opt-in two-container IEEE1905 lab: no changes to A/C, Wi-Fi, or host management IF."""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import shlex
from pathlib import Path, PurePosixPath
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


def validate_install_tree(path: Path) -> Path:
    """Check a prebuilt upstream install tree before creating any Docker resources."""
    try:
        root = path.resolve(strict=True)
    except OSError:
        raise LabError("prplMesh install tree unavailable") from None
    if (not root.is_dir()
            or not (root / "scripts/prplmesh_utils.sh").is_file()
            or not (root / "bin/beerocks_agent").is_file()
            or not (root / "bin/beerocks_controller").is_file()):
        raise LabError("prplMesh install tree requires scripts/prplmesh_utils.sh and agent/controller binaries")
    return root


def stage_private_platform_db(source: Path, destination_install: Path) -> None:
    """Copy one private node configuration only into a disposable install tree."""
    info = source.lstat()
    if (source.is_symlink() or not source.is_file()
            or info.st_uid != os.geteuid() or info.st_mode & 0o077
            or info.st_size > 1024 * 1024):
        raise LabError("private platform DB must be owned by caller, mode 0600")
    content = source.read_bytes()
    if not content or b"\x00" in content:
        raise LabError("invalid private platform DB")
    # Accept only effective key=value lines, not comments or substring matches.
    # This protects the lab from silently retrying missing radio slots 2/3.
    text = content.decode("utf-8")
    entries = {}
    for line in text.splitlines():
        value = line.strip()
        if not value or value.startswith("#"):
            continue
        if "=" not in value:
            continue
        key, setting = [part.strip() for part in value.split("=", 1)]
        if key in entries:
            raise LabError("duplicate lab platform DB key: " + key)
        entries[key] = setting
    if entries.get("backhaul_wire_iface") != "eth0":
        raise LabError("lab platform DB must explicitly track Docker eth0")
    radios = [entries.get("wireless_interface_" + str(i), "") for i in range(4)]
    if (any(not re.fullmatch(r"[A-Za-z0-9_.-]{1,15}", item) for item in radios)
            or len(set(radios)) != 4):
        raise LabError("lab platform DB requires four distinct mapped radio slots 0..3")
    if "@RADIO" in text or "@STA" in text or "REPLACE_WITH" in text:
        raise LabError("unconfigured lab platform DB placeholder")
    target = destination_install / "lab/prplmesh_platform_db"
    target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    target.write_bytes(content)
    target.chmod(0o600)


def stage_architecture(root: Path) -> str:
    """Prevent feeding an AArch64 cross-build to an x86 Docker runner (or vice versa)."""
    if not shutil.which("readelf"):
        raise LabError("readelf required for runner/ELF architecture preflight")
    machines = set()
    binaries = [root / "bin" / name for name in
                ("beerocks_agent", "beerocks_controller", "ieee1905_transport")]
    amx_module = root / "lib/amxb/mod-amxb-ubus.so"
    if amx_module.is_file():
        # The backend is dlopen()'d at runtime; its machine type must agree.
        binaries.append(amx_module)
    for binary in binaries:
        result = command(["readelf", "-h", str(binary)])
        match = re.search(r"(?m)^\s*Machine:\s*(.+?)\s*$", result)
        if not match:
            raise LabError("ELF machine unavailable from staged prplMesh binary")
        machines.add(match.group(1))
    if machines == {"AArch64"}:
        return "arm64"
    if machines == {"Advanced Micro Devices X86-64"}:
        return "amd64"
    raise LabError("mixed or unsupported prplMesh install-tree ELF architecture")


def validate_install_target(target: str) -> str:
    """Preserve an upstream binary's compiled CMAKE_INSTALL_PREFIX in its container."""
    path = PurePosixPath(target)
    if (not target.startswith("/") or target == "/" or ".." in target.split("/")
            or any(char in target for char in ",:\n") or
            path.parts[1:2] in (("proc",), ("sys",), ("dev",))):
        raise LabError("unsafe absolute install target inside container")
    return str(path)


def run_container(name: str, network: str, image: str, startup: str,
                  install_tree: Path | None = None, bridge_al: bytes | None = None,
                  install_target: str = "/opt/t6-prplmesh",
                  amx_ubus: bool = False) -> str:
    argv = [
        "docker", "run", "--detach", "--rm", "--name", name,
        "--network", network, "--cap-add=NET_RAW", "--cap-add=NET_ADMIN",
        "--security-opt=no-new-privileges", "--pull=never",
    ]
    if install_tree is not None:
        # Upstream runner's entrypoint needs INSTALL_DIR and a mounted install
        # tree. Mount separate scratch copies, never the original build output.
        if any(char in str(install_tree) for char in ",:\n"):
            raise LabError("unsafe character in install tree mount path")
        target = validate_install_target(install_target)
        argv += ["--mount", f"type=bind,source={install_tree},target={target}",
                 "--env", f"INSTALL_DIR={target}"]
    if amx_ubus and (install_tree is None or bridge_al is None):
        raise LabError("AMX UBus requires staged install and pinned isolated AL identity")
    if bridge_al is not None:
        if install_tree is None:
            raise LabError("fixed bridge identity requires the upstream install-tree runner")
        # Old upstream runner's entrypoint executes /bin/bash "$@". Set the
        # bridge identity only *inside* this disposable network namespace,
        # before starting prplMesh. Re-apply on Agent restart.
        al = ":".join(f"{byte:02x}" for byte in bridge_al)
        argv += ["--env", f"T6_AL_MAC={al}"]
        if amx_ubus:
            # Only the disposable container interfaces are modified; its
            # Docker eth0 is attached to the local bridge for wired 1905.
            # Install a separate, private platform DB for each node.
            command_prefix = (
                '(ip link show dev br-lan >/dev/null 2>&1 || '
                'ip link add name br-lan type bridge) && '
                'ip link show dev eth0 >/dev/null && '
                'ip link set dev eth0 master br-lan && '
                'ip link set dev eth0 up && '
                'ip link set dev br-lan address "$T6_AL_MAC" && '
                'ip link set dev br-lan up && '
                'mkdir -p /tmp/beerocks /var/run && '
                'cp "$INSTALL_DIR/lab/prplmesh_platform_db" '
                '/tmp/beerocks/prplmesh_platform_db && '
                'chmod 600 /tmp/beerocks/prplmesh_platform_db && '
                'test -r "$INSTALL_DIR/lib/amxb/mod-amxb-ubus.so" && '
                'command -v ubusd >/dev/null && '
                '(ubusd -s /var/run/ubus.sock >/dev/null 2>&1 &) && '
                'sleep 1 && test -S /var/run/ubus.sock && ')
        else:
            command_prefix = 'ip link set dev br-lan address "$T6_AL_MAC" && '
        return command([*argv, image, "-c", command_prefix + 'exec ' + startup])
    return command([*argv, image, startup])


def bridge_al_mac(container: str, verifier) -> bytes:
    """Read an independent container's actual br-lan identity, not a guessed MAC."""
    value = command(["docker", "exec", container, "cat", "/sys/class/net/br-lan/address"])
    try:
        result = verifier.mac_bytes(value)
    except verifier.CaptureError:
        raise LabError("invalid br-lan MAC in running prplMesh container") from None
    if result[0] & 1:
        raise LabError("container br-lan MAC must be unicast")
    return result


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


def save_private_docker_log(container: str, path: Path) -> None:
    """Best-effort private startup evidence before --rm destroys a container."""
    try:
        proc = subprocess.run(["docker", "logs", "--tail", "1000", container],
                              capture_output=True, text=True, timeout=15, check=False)
        if proc.returncode == 0:
            path.write_text(proc.stdout + proc.stderr)
            path.chmod(0o600)
    except (OSError, subprocess.TimeoutExpired):
        pass


def running_elf_names(container: str) -> set[str]:
    """Inspect the actual /proc executable targets, not names in ps arguments."""
    listing = command(["docker", "exec", container, "sh", "-c",
                       'for p in /proc/[0-9]*; do readlink "$p/exe" 2>/dev/null || :; done'])
    return {Path(path).name for path in listing.splitlines() if path.startswith("/")}


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
    if args.auto_al:
        if args.controller_al or args.agent_al:
            raise LabError("--auto-al cannot be combined with explicit AL MACs")
        ctrl_al = agent_al = None
    else:
        if not args.controller_al or not args.agent_al:
            raise LabError("both AL MACs required unless --auto-al is selected")
        ctrl_al = verifier.mac_bytes(args.controller_al)
        agent_al = verifier.mac_bytes(args.agent_al)
        if ctrl_al == agent_al or ctrl_al[0] & 1 or agent_al[0] & 1:
            raise LabError("two distinct unicast AL MACs are required")
    source_tree = validate_install_tree(args.install_tree) if args.install_tree else None
    if source_tree is not None:
        validate_install_target(args.install_target)
    if args.amx_ubus:
        if source_tree is None:
            raise LabError("--amx-ubus requires --install-tree")
        backend = source_tree / "lib/amxb/mod-amxb-ubus.so"
        if not backend.is_file() or not backend.stat().st_size:
            raise LabError("missing staged AMXRT UBus backend module")
        if not args.controller_platform_db or not args.agent_platform_db:
            raise LabError("--amx-ubus requires two distinct private platform DB files")
        if args.controller_platform_db.resolve() == args.agent_platform_db.resolve():
            raise LabError("Controller and Agent must use separate platform DB sources")
    os.umask(0o077)
    if args.output.exists() or args.output.is_symlink():
        raise LabError("choose a new private output directory")
    if source_tree is not None and (args.output.resolve().is_relative_to(source_tree)):
        raise LabError("private output cannot be inside source install tree")
    args.output.mkdir(parents=True, mode=0o700)
    if not args.output.is_dir() or args.output.is_symlink():
        raise LabError("unsafe output directory")
    args.output = args.output.resolve(strict=True)
    for probe in plan_images(args.controller_image, args.agent_image):
        command(probe)
    runner_arch = None
    if source_tree is not None:
        runner_arch = stage_architecture(source_tree)
        for image in (args.controller_image, args.agent_image):
            image_arch = command(["docker", "image", "inspect", "--format",
                                  "{{.Architecture}}", image])
            if image_arch != runner_arch:
                raise LabError("prplMesh install ELF and runner image architecture mismatch")
    # Keep upstream-installed binaries and config independent per node. The
    # caller's original (possibly private) build tree is never mounted mutable.
    controller_tree = agent_tree = None
    if source_tree is not None:
        controller_tree = args.output / "controller-install"
        agent_tree = args.output / "agent-install"
        shutil.copytree(source_tree, controller_tree, symlinks=True)
        shutil.copytree(source_tree, agent_tree, symlinks=True)
        if args.amx_ubus:
            stage_private_platform_db(args.controller_platform_db, controller_tree)
            stage_private_platform_db(args.agent_platform_db, agent_tree)
    tag = secrets.token_hex(3)
    network, bridge = "t6mesh-" + tag, "t6m" + tag
    controller, agent = network + "-c", network + "-a"
    resources = {"network": False, "controller": False, "agent": False}
    result = {
        "environment": "dedicated-container-lab",
        "network_isolation": "docker-internal",
        "runner_binary_architecture_match": runner_arch is not None,
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
            nonlocal ctrl_al, agent_al
            run_container(controller, network, args.controller_image, "start-controller-agent",
                          controller_tree, ctrl_al if source_tree is not None else None,
                          args.install_target, amx_ubus=args.amx_ubus)
            resources["controller"] = True
            run_container(agent, network, args.agent_image, "start-agent", agent_tree,
                          agent_al if source_tree is not None else None,
                          args.install_target, amx_ubus=args.amx_ubus)
            resources["agent"] = True
            if not (container_running(controller) and container_running(agent)):
                raise LabError("at least one node stopped before initial capture")
            result["controller_processes_running"] = wait_for_processes(
                controller, ("ieee1905_transport", "beerocks_controller", "beerocks_agent"))
            result["agent_processes_running"] = wait_for_processes(
                agent, ("ieee1905_transport", "beerocks_agent"))
            if not (result["controller_processes_running"] and result["agent_processes_running"]):
                raise LabError("prplMesh processes not observed in both independent nodes")
            ctrl_exes = running_elf_names(controller)
            agent_exes = running_elf_names(agent)
            result["real_prplmesh_binary_confirmed"] = (
                {"ieee1905_transport", "beerocks_controller", "beerocks_agent"} <= ctrl_exes
                and {"ieee1905_transport", "beerocks_agent"} <= agent_exes)
            if not result["real_prplmesh_binary_confirmed"]:
                raise LabError("actual prplMesh executable paths missing from /proc")
            actual_ctrl = bridge_al_mac(controller, verifier)
            actual_agent = bridge_al_mac(agent, verifier)
            if args.auto_al:
                ctrl_al, agent_al = actual_ctrl, actual_agent
                if ctrl_al == agent_al:
                    raise LabError("both prplMesh bridges have the same AL MAC")
            elif source_tree is not None and (actual_ctrl != ctrl_al or actual_agent != agent_al):
                raise LabError("actual bridge AL MAC does not match pinned runner identity")

        capture(bridge, args.output / "initial.ieee1905.pcap", args.duration,
                during_capture=start_pair)
        first = assess_capture(args.output / "initial.ieee1905.pcap", ctrl_al, agent_al)
        result["baseline_wire_topology"] = first["wire_topology_exchange"]
        result["baseline_message_types"] = first["message_type_counts"]
        if args.controller_db_command:
            result["controller_database_initial"] = agent_in_controller_db(
                controller, args.controller_db_command, agent_al)

        save_private_docker_log(agent, args.output / "agent-before-stop.docker.log")
        command(["docker", "stop", agent], timeout=25)
        resources["agent"] = False
        if not container_running(controller):
            raise LabError("controller exited during agent outage")
        capture(bridge, args.output / "agent-stopped.ieee1905.pcap", args.outage)
        if args.controller_db_command:
            result["controller_database_after_agent_stop"] = agent_in_controller_db(
                controller, args.controller_db_command, agent_al)

        def restart_agent():
            run_container(agent, network, args.agent_image, "start-agent", agent_tree,
                          agent_al if source_tree is not None else None,
                          args.install_target, amx_ubus=args.amx_ubus)
            resources["agent"] = True
            if not container_running(agent) or not wait_for_processes(
                    agent, ("ieee1905_transport", "beerocks_agent")):
                raise LabError("agent process failed to restart")
            if not {"ieee1905_transport", "beerocks_agent"} <= running_elf_names(agent):
                raise LabError("prplMesh ELF processes missing after Agent restart")
            if bridge_al_mac(agent, verifier) != agent_al:
                raise LabError("Agent AL MAC changed across restart; recovery cannot be proven")

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
                save_private_docker_log(name, args.output / f"{key}-final.docker.log")
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
    ap.add_argument("--controller-al", help="explicit Controller AL MAC")
    ap.add_argument("--agent-al", help="explicit Agent AL MAC")
    ap.add_argument("--auto-al", action="store_true",
                    help="derive AL MACs from the two live br-lan interfaces")
    ap.add_argument("--install-tree", type=Path,
                    help="existing prplMesh build/install; copied per node, never mounted directly")
    ap.add_argument("--install-target", default="/opt/t6-prplmesh",
                    help="in-container CMAKE_INSTALL_PREFIX; use the compiled path if absolute")
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--controller-db-command", help="optional in-container CLI command, e.g. beerocks_cli -c bml_conn_map")
    ap.add_argument("--amx-ubus", action="store_true",
                    help="isolated lab: require staged backend and per-node ubusd")
    ap.add_argument("--controller-platform-db", type=Path,
                    help="private controller node DB; copied to disposable container tree")
    ap.add_argument("--agent-platform-db", type=Path,
                    help="private agent node DB; copied to disposable container tree")
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
        if args.output.is_dir() and not args.output.is_symlink():
            failure = {"verdict": "NOT_PROVEN", "reason": str(exc),
                       "real_prplmesh_1905_proven": False}
            (args.output / "failure.json").write_text(
                json.dumps(failure, indent=2, sort_keys=True) + "\n")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
